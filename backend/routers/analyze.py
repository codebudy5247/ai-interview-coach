"""
routers/analyze.py
------------------
All API route handlers for the interview-coach pipeline.

Endpoints:
  POST   /api/analyze              — Upload MP3 + question → start pipeline → return session_id
  GET    /api/feedback/{session_id} — Return stored feedback JSON
  GET    /api/report/{session_id}   — Download .txt feedback report
  DELETE /api/cleanup/{session_id}  — Remove temp files + session data
"""

import uuid
import threading

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from models.schemas import AnalyzeResponse, CleanupResponse
from utils.file_handler import (
    save_upload,
    delete_temp,
    get_report_path,
    format_feedback_txt,
    save_report_txt,
)
from services.whisper_service import transcribe
from services.feedback_service import get_feedback, FeedbackServiceError

router = APIRouter(prefix="/api", tags=["analyze"])

# ---------------------------------------------------------------------------
# In-memory session store
# Key: session_id  →  dict with status, feedback, transcript, error
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}


def get_session(session_id: str) -> dict:
    """Retrieve a session or raise 404."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


# ---------------------------------------------------------------------------
# Pipeline runner — runs in a background thread
# ---------------------------------------------------------------------------
def _run_pipeline(session_id: str) -> None:
    """
    Full AI pipeline executed in a background thread so the POST /api/analyze
    endpoint can return immediately with the session_id.

    Steps:
      1. Transcribe MP3 with Whisper
      2. Generate feedback via Gemini → Ollama fallback (with retries)
      3. Store results in _sessions[session_id]
      4. Clean up temp MP3
    """
    session = _sessions.get(session_id)
    if session is None:
        return

    mp3_path = session["mp3_path"]
    question = session["question"]

    try:
        # --- Step 1: Transcribe ---
        _sessions[session_id]["status"] = "transcribing"
        print(f"[pipeline:{session_id[:8]}] Transcribing...")
        transcript = transcribe(mp3_path)
        _sessions[session_id]["transcript"] = transcript
        print(f"[pipeline:{session_id[:8]}] Transcription done.")

        # --- Step 2: Generate feedback ---
        _sessions[session_id]["status"] = "analyzing"
        print(f"[pipeline:{session_id[:8]}] Generating feedback...")
        feedback = get_feedback(question, transcript)
        # Attach transcript to feedback so /api/feedback returns it too
        feedback["transcript"] = transcript
        _sessions[session_id]["feedback"] = feedback
        print(f"[pipeline:{session_id[:8]}] Feedback ready.")

        # --- Step 3: Save .txt report (Phase 4) ---
        _sessions[session_id]["status"] = "saving_report"
        print(f"[pipeline:{session_id[:8]}] Saving feedback report...")
        formatted = format_feedback_txt(feedback, question, transcript, session_id)
        report_path = save_report_txt(formatted, session_id)
        _sessions[session_id]["report_path"] = str(report_path)
        print(f"[pipeline:{session_id[:8]}] Report saved → {report_path}")

        _sessions[session_id]["status"] = "done"

    except FeedbackServiceError as exc:
        print(f"[pipeline:{session_id[:8]}] FeedbackServiceError: {exc}")
        _sessions[session_id]["status"] = "error"
        _sessions[session_id]["error"] = str(exc)

    except Exception as exc:
        print(f"[pipeline:{session_id[:8]}] Unexpected error: {exc}")
        _sessions[session_id]["status"] = "error"
        _sessions[session_id]["error"] = f"Pipeline failed: {exc}"

    finally:
        # --- Step 4: Clean up temp MP3 ---
        delete_temp(session_id)
        print(f"[pipeline:{session_id[:8]}] Temp MP3 deleted.")


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    background_tasks: BackgroundTasks,
    question: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    - Save the uploaded MP3 to temp/
    - Register the session
    - Kick off the AI pipeline in a background thread
    - Return session_id immediately
    """
    session_id = str(uuid.uuid4())

    # Save MP3
    mp3_path = await save_upload(audio, session_id)

    # Register session
    _sessions[session_id] = {
        "question": question,
        "mp3_path": str(mp3_path),
        "status": "uploaded",
        "feedback": None,
        "transcript": None,
        "report_path": None,
        "error": None,
    }

    # Run pipeline in a background thread (Whisper + Gemini/Ollama are blocking/CPU-bound)
    thread = threading.Thread(
        target=_run_pipeline,
        args=(session_id,),
        daemon=True,
        name=f"pipeline-{session_id[:8]}",
    )
    thread.start()

    return AnalyzeResponse(session_id=session_id)


# ---------------------------------------------------------------------------
# GET /api/feedback/{session_id}
# ---------------------------------------------------------------------------
@router.get("/feedback/{session_id}")
async def get_feedback_endpoint(session_id: str):
    """
    Return the feedback JSON once the pipeline is done.
    Returns 202 while still processing, 500 if the pipeline errored.
    """
    session = get_session(session_id)
    status = session["status"]

    if status == "error":
        raise HTTPException(
            status_code=500,
            detail=session.get("error", "Pipeline failed."),
        )
    if session["feedback"] is None:
        raise HTTPException(
            status_code=202,
            detail=f"Processing in progress. Status: {status}",
        )
    return session["feedback"]


# ---------------------------------------------------------------------------
# GET /api/status/{session_id}  — lightweight polling endpoint
# ---------------------------------------------------------------------------
@router.get("/status/{session_id}")
async def get_status(session_id: str):
    """
    Return the current pipeline status for a session.
    Statuses: uploaded → transcribing → analyzing → done | error
    """
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "status": session["status"],
        "error": session.get("error"),
    }


# ---------------------------------------------------------------------------
# GET /api/report/{session_id}
# ---------------------------------------------------------------------------
@router.get("/report/{session_id}")
async def download_report(session_id: str):
    """
    Serve the saved .txt feedback report as a file download.

    Returns:
        200  FileResponse  — report is ready; browser will download it.
        202  JSON          — pipeline is still running (report not yet saved).
        500  JSON          — pipeline ended in an error.
        404  JSON          — session not found or report file missing.
    """
    session = get_session(session_id)  # raises 404 if session unknown
    status = session["status"]

    if status == "error":
        raise HTTPException(
            status_code=500,
            detail=session.get("error", "Pipeline failed — no report generated."),
        )

    if status != "done":
        raise HTTPException(
            status_code=202,
            detail=f"Report not ready yet. Current status: {status}",
        )

    path = get_report_path(session_id)  # raises 404 if file missing
    return FileResponse(
        path=str(path),
        media_type="text/plain",
        filename=f"{session_id[:8]}_feedback.txt",
    )


# ---------------------------------------------------------------------------
# DELETE /api/cleanup/{session_id}
# ---------------------------------------------------------------------------
@router.delete("/cleanup/{session_id}", response_model=CleanupResponse)
async def cleanup(session_id: str):
    """Remove temp MP3 and session data."""
    delete_temp(session_id)
    _sessions.pop(session_id, None)
    return CleanupResponse(success=True)
