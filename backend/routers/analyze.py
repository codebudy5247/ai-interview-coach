"""
routers/analyze.py
------------------
All API route handlers for the interview-coach pipeline.

Endpoints:
  POST   /api/analyze              — Upload MP3 + question → start pipeline → return session_id
  GET    /api/progress/{session_id} — SSE stream of pipeline progress events
  GET    /api/feedback/{session_id} — Return stored feedback JSON
  DELETE /api/cleanup/{session_id}  — Remove temp files + session data
"""

import uuid
import threading
import queue
import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from models.schemas import AnalyzeResponse, CleanupResponse, SSEEvent
from utils.file_handler import (
    save_upload,
    delete_temp,
)
from services.whisper_service import transcribe
from services.feedback_service import get_feedback, FeedbackServiceError
from services.imagekit_service import upload_audio, delete_audio
from database import SessionLocal
from models.session_model import InterviewSession

router = APIRouter(prefix="/api", tags=["analyze"])

# ---------------------------------------------------------------------------
# In-memory session store
# Key: session_id  →  dict with status, feedback, transcript, error, events queue
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}


def get_session(session_id: str) -> dict:
    """Retrieve a session or raise 404."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


def _emit_sse(session_id: str, step: str, status: str, message: str) -> None:
    """Add an SSE event to the session's event queue."""
    session = _sessions.get(session_id)
    if session and "events" in session:
        event = SSEEvent(step=step, status=status, message=message)
        session["events"].put(event)
        print(f"[sse:{session_id[:8]}] {step}: {status} — {message}")


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

    # Track imagekit file_id for cleanup if pipeline fails after upload
    imagekit_file_id = None

    try:
        # --- Step 1: Transcribe ---
        _sessions[session_id]["status"] = "transcribing"
        _emit_sse(session_id, "transcribing", "in_progress", "Transcribing your audio...")
        print(f"[pipeline:{session_id[:8]}] Transcribing...")
        transcript = transcribe(mp3_path)
        _sessions[session_id]["transcript"] = transcript
        _emit_sse(session_id, "transcribing", "done", "Transcription complete")
        print(f"[pipeline:{session_id[:8]}] Transcription done.")

        # --- Step 1b: Upload audio to ImageKit (Phase 2) ---
        _sessions[session_id]["status"] = "uploading_audio"
        _emit_sse(session_id, "uploading_audio", "in_progress", "Uploading audio to cloud...")
        print(f"[pipeline:{session_id[:8]}] Uploading audio to ImageKit...")
        file_name = f"{session_id}.mp3"
        upload_result = upload_audio(mp3_path, file_name)
        audio_url = upload_result["url"]
        imagekit_file_id = upload_result["file_id"]
        _sessions[session_id]["audio_url"] = audio_url
        _sessions[session_id]["imagekit_file_id"] = imagekit_file_id
        _emit_sse(session_id, "uploading_audio", "done", "Audio uploaded to cloud")
        print(f"[pipeline:{session_id[:8]}] Audio uploaded → {audio_url}")

        # --- Step 2: Generate feedback ---
        _sessions[session_id]["status"] = "analyzing"
        _emit_sse(session_id, "analyzing", "in_progress", "Analyzing with AI...")
        print(f"[pipeline:{session_id[:8]}] Generating feedback...")
        # Callback to emit SSE events during feedback generation (for retries)
        def feedback_status_callback(provider: str, attempt: int, status: str, message: str):
            _emit_sse(session_id, "analyzing", status, message)

        feedback = get_feedback(question, transcript, on_status=feedback_status_callback)
        # Attach transcript and audio_url to feedback so /api/feedback returns it too
        feedback["transcript"] = transcript
        feedback["audio_url"] = audio_url
        feedback["imagekit_file_id"] = imagekit_file_id
        _sessions[session_id]["feedback"] = feedback
        _emit_sse(session_id, "analyzing", "done", "Feedback generated")
        print(f"[pipeline:{session_id[:8]}] Feedback ready.")

        # --- Step 3: Persist to database ---
        _sessions[session_id]["status"] = "persisting"
        _emit_sse(session_id, "persisting", "in_progress", "Saving to history...")
        print(f"[pipeline:{session_id[:8]}] Persisting session to database...")
        db = SessionLocal()
        try:
            db_session = InterviewSession(
                id=session_id,
                question=question,
                transcript=transcript,
                overall_score=feedback["overall_score"],
                feedback_json=json.dumps(feedback),
            )
            db.add(db_session)
            db.commit()
            print(f"[pipeline:{session_id[:8]}] Session persisted to DB.")
        finally:
            db.close()

        _sessions[session_id]["status"] = "done"
        _emit_sse(session_id, "done", "done", "DONE")

    except FeedbackServiceError as exc:
        print(f"[pipeline:{session_id[:8]}] FeedbackServiceError: {exc}")
        # Rollback: delete uploaded audio if ImageKit upload succeeded
        if imagekit_file_id:
            print(f"[pipeline:{session_id[:8]}] Rolling back: deleting audio from ImageKit...")
            delete_audio(imagekit_file_id)
        _sessions[session_id]["status"] = "error"
        _sessions[session_id]["error"] = str(exc)
        _emit_sse(session_id, "error", "error", str(exc))

    except Exception as exc:
        print(f"[pipeline:{session_id[:8]}] Unexpected error: {exc}")
        # Rollback: delete uploaded audio if ImageKit upload succeeded
        if imagekit_file_id:
            print(f"[pipeline:{session_id[:8]}] Rolling back: deleting audio from ImageKit...")
            delete_audio(imagekit_file_id)
        _sessions[session_id]["status"] = "error"
        _sessions[session_id]["error"] = f"Pipeline failed: {exc}"
        _emit_sse(session_id, "error", "error", f"Pipeline failed: {exc}")

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
        "error": None,
        "events": queue.Queue(),
    }

    # Emit initial event
    _emit_sse(session_id, "uploaded", "done", "Audio uploaded")

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
# GET /api/progress/{session_id} — SSE stream
# ---------------------------------------------------------------------------
@router.get("/progress/{session_id}")
async def get_progress_stream(session_id: str):
    """
    SSE endpoint that streams pipeline progress events.
    Yields events as JSON lines: {"step": "...", "status": "...", "message": "..."}
    """
    session = get_session(session_id)
    events_queue: queue.Queue = session.get("events")

    if events_queue is None:
        raise HTTPException(status_code=404, detail="Session has no events queue.")

    async def event_generator():
        while True:
            # Check if session still exists
            if session_id not in _sessions:
                break

            # Try to get an event from the queue (non-blocking)
            try:
                event = events_queue.get_nowait()
                yield f"data: {event.model_dump_json()}\n\n"

                # Stop streaming only after final "done" or "error" step
                if event.step in ("done", "error"):
                    break
            except queue.Empty:
                # Queue is empty — check if pipeline already finished
                current_status = _sessions.get(session_id, {}).get("status")
                if current_status in ("done", "error"):
                    # Drain any remaining events that arrived between checks
                    await asyncio.sleep(0.1)
                    while True:
                        try:
                            event = events_queue.get_nowait()
                            yield f"data: {event.model_dump_json()}\n\n"
                            if event.step in ("done", "error"):
                                return
                        except queue.Empty:
                            return  # nothing left, close stream

            # Wait before checking again
            await asyncio.sleep(0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
# DELETE /api/cleanup/{session_id}
# ---------------------------------------------------------------------------
@router.delete("/cleanup/{session_id}", response_model=CleanupResponse)
async def cleanup(session_id: str):
    """Remove temp MP3 and session data."""
    delete_temp(session_id)
    _sessions.pop(session_id, None)
    return CleanupResponse(success=True)
