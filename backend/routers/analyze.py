"""
routers/analyze.py
------------------
All API route handlers for the interview-coach pipeline.

Endpoints:
  POST   /api/analyze              — Upload audio + question → start pipeline → return session_id
  GET    /api/progress/{session_id} — SSE stream of pipeline progress events
  GET    /api/feedback/{session_id} — Return stored feedback JSON
  DELETE /api/cleanup/{session_id}  — Remove temp files + session data
"""

import uuid
import threading
import queue
import asyncio
import json
import logging
import os
import time

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

import config
from models.schemas import AnalyzeResponse, CleanupResponse, SSEEvent, StatusResponse, FeedbackResponse
from utils.file_handler import save_upload, delete_temp
from services.whisper_service import transcribe
from services.feedback_service import get_feedback, FeedbackServiceError
from services.imagekit_service import upload_audio, delete_audio
from database import SessionLocal
from models.session_model import InterviewSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["analyze"])

# ---------------------------------------------------------------------------
# In-memory session store (volatile pipeline state).
# Key: session_id → dict with status, feedback, transcript, error, events queue,
# created_at. Structural changes (insert / evict / pop) are guarded by a lock;
# per-field mutations from the single owning pipeline thread are GIL-atomic.
# ---------------------------------------------------------------------------
_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


_FINISHED_STATUSES = ("done", "error")


def _evict_locked() -> None:
    """Prune expired + overflow sessions. Caller must hold _sessions_lock.

    Only finished (done/error) sessions are ever evicted, so an in-flight
    pipeline is never popped out from under its running thread.
    """
    now = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if s.get("status") in _FINISHED_STATUSES
        and now - s.get("created_at", now) > config.SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)

    if len(_sessions) > config.SESSION_STORE_MAX:
        finished = sorted(
            (s.get("created_at", 0.0), sid)
            for sid, s in _sessions.items()
            if s.get("status") in _FINISHED_STATUSES
        )
        overflow = len(_sessions) - config.SESSION_STORE_MAX
        for _, sid in finished[:overflow]:
            _sessions.pop(sid, None)


def get_session(session_id: str) -> dict:
    """Retrieve a session or raise 404."""
    with _sessions_lock:
        session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session


def _emit_sse(session_id: str, step: str, status: str, message: str) -> None:
    """Add an SSE event to the session's event queue."""
    session = _sessions.get(session_id)
    if session and "events" in session:
        session["events"].put(SSEEvent(step=step, status=status, message=message))
        logger.info("[sse:%s] %s: %s — %s", session_id[:8], step, status, message)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------
def _rollback_imagekit(session_id: str, imagekit_file_id: str | None) -> None:
    """Delete the uploaded audio from ImageKit if the pipeline failed after upload."""
    if imagekit_file_id:
        logger.info("[pipeline:%s] Rolling back: deleting audio from ImageKit...", session_id[:8])
        delete_audio(imagekit_file_id)


def _persist_session(session_id: str, question, transcript, feedback, code_snippet, code_language) -> None:
    """Persist a completed session to the database (background thread → manual session)."""
    db = SessionLocal()
    try:
        db.add(InterviewSession(
            id=session_id,
            question=question,
            transcript=transcript,
            overall_score=feedback["overall_score"],
            feedback_json=json.dumps(feedback),
            code_snippet=code_snippet,
            code_language=code_language,
        ))
        db.commit()
        logger.info("[pipeline:%s] Session persisted to DB.", session_id[:8])
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pipeline runner — runs in a background thread
# ---------------------------------------------------------------------------
def _run_pipeline(session_id: str) -> None:
    """
    Full AI pipeline executed in a background thread so the POST /api/analyze
    endpoint can return immediately with the session_id.

    Steps:
      1. Transcribe audio with Whisper
      2. Generate feedback via Azure OpenAI → Gemini fallback (with retries)
      3. Persist results to the database
      4. Clean up temp audio file
    """
    session = _sessions.get(session_id)
    if session is None:
        return

    audio_path = session["audio_path"]
    question = session["question"]
    code_snippet = session.get("code_snippet")
    code_language = session.get("code_language")

    # Track imagekit file_id for cleanup if pipeline fails after upload
    imagekit_file_id = None

    try:
        # --- Step 1: Transcribe ---
        session["status"] = "transcribing"
        _emit_sse(session_id, "transcribing", "in_progress", "Transcribing your audio...")
        transcript = transcribe(audio_path)
        session["transcript"] = transcript
        _emit_sse(session_id, "transcribing", "done", "Transcription complete")

        # --- Step 1b: Upload audio to ImageKit ---
        session["status"] = "uploading_audio"
        _emit_sse(session_id, "uploading_audio", "in_progress", "Uploading audio to cloud...")
        file_name = f"{session_id}{os.path.splitext(audio_path)[1]}"
        upload_result = upload_audio(audio_path, file_name)
        audio_url = upload_result["url"]
        imagekit_file_id = upload_result["file_id"]
        session["audio_url"] = audio_url
        session["imagekit_file_id"] = imagekit_file_id
        _emit_sse(session_id, "uploading_audio", "done", "Audio uploaded to cloud")
        logger.info("[pipeline:%s] Audio uploaded → %s", session_id[:8], audio_url)

        # --- Step 2: Generate feedback ---
        session["status"] = "analyzing"
        _emit_sse(session_id, "analyzing", "in_progress", "Analyzing with AI...")

        def feedback_status_callback(provider: str, attempt: int, status: str, message: str):
            _emit_sse(session_id, "analyzing", status, message)

        feedback = get_feedback(
            question,
            transcript,
            code_snippet=code_snippet,
            code_language=code_language,
            on_status=feedback_status_callback,
        )
        # Attach extra fields so /api/feedback returns them too
        feedback["transcript"] = transcript
        feedback["audio_url"] = audio_url
        feedback["imagekit_file_id"] = imagekit_file_id
        feedback["code_snippet"] = code_snippet
        feedback["code_language"] = code_language
        session["feedback"] = feedback
        _emit_sse(session_id, "analyzing", "done", "Feedback generated")

        # --- Step 3: Persist to database ---
        session["status"] = "persisting"
        _emit_sse(session_id, "persisting", "in_progress", "Saving to history...")
        _persist_session(session_id, question, transcript, feedback, code_snippet, code_language)

        session["status"] = "done"
        _emit_sse(session_id, "done", "done", "DONE")

    except FeedbackServiceError as exc:
        logger.warning("[pipeline:%s] FeedbackServiceError: %s", session_id[:8], exc)
        _rollback_imagekit(session_id, imagekit_file_id)
        session["status"] = "error"
        session["error"] = str(exc)
        _emit_sse(session_id, "error", "error", str(exc))

    except Exception as exc:
        logger.exception("[pipeline:%s] Unexpected error", session_id[:8])
        _rollback_imagekit(session_id, imagekit_file_id)
        session["status"] = "error"
        session["error"] = f"Pipeline failed: {exc}"
        _emit_sse(session_id, "error", "error", f"Pipeline failed: {exc}")

    finally:
        # --- Step 4: Clean up temp audio ---
        delete_temp(session_id)
        logger.info("[pipeline:%s] Temp audio deleted.", session_id[:8])


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
    code_snippet: str = Form(None),
    code_language: str = Form(None),
):
    """
    - Save the uploaded audio file to temp/
    - Register the session
    - Kick off the AI pipeline in a background thread
    - Return session_id immediately
    """
    # --- Light input validation (cheap guards before any heavy work) ---
    if not question.strip():
        raise HTTPException(status_code=400, detail="question must not be blank.")
    if len(question) > config.MAX_QUESTION_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"question exceeds {config.MAX_QUESTION_LEN} characters.",
        )
    # Fast reject when the size is known up front (UploadFile.size may be None).
    if audio.size is not None and audio.size > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"audio file exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )
    if code_snippet and len(code_snippet) > config.MAX_CODE_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"code_snippet exceeds {config.MAX_CODE_LEN} characters.",
        )

    session_id = str(uuid.uuid4())

    # Save Audio
    audio_path = await save_upload(audio, session_id)

    # Authoritative size check on the written bytes (covers size=None uploads).
    if os.path.getsize(audio_path) > config.MAX_UPLOAD_BYTES:
        delete_temp(session_id)
        raise HTTPException(
            status_code=400,
            detail=f"audio file exceeds {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    code_snippet = code_snippet.strip() if code_snippet and code_snippet.strip() else None

    # Register session (lock guards structural insert + eviction)
    with _sessions_lock:
        _evict_locked()
        _sessions[session_id] = {
            "question": question,
            "audio_path": str(audio_path),
            "code_snippet": code_snippet,
            "code_language": code_language,
            "status": "uploaded",
            "feedback": None,
            "transcript": None,
            "error": None,
            "events": queue.Queue(),
            "created_at": time.time(),
        }

    # Emit initial event
    _emit_sse(session_id, "uploaded", "done", "Audio uploaded")

    # Run pipeline in a background thread (Whisper + Azure/Gemini are blocking/CPU-bound)
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
                    await asyncio.sleep(config.SSE_DRAIN_DELAY)
                    while True:
                        try:
                            event = events_queue.get_nowait()
                            yield f"data: {event.model_dump_json()}\n\n"
                            if event.step in ("done", "error"):
                                return
                        except queue.Empty:
                            return  # nothing left, close stream

            # Wait before checking again
            await asyncio.sleep(config.SSE_POLL_INTERVAL)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/feedback/{session_id}
# ---------------------------------------------------------------------------
@router.get("/feedback/{session_id}", response_model=FeedbackResponse)
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
@router.get("/status/{session_id}", response_model=StatusResponse)
async def get_status(session_id: str):
    """
    Return the current pipeline status for a session.
    Statuses: uploaded → transcribing → analyzing → done | error
    """
    session = get_session(session_id)
    return StatusResponse(
        session_id=session_id,
        status=session["status"],
        error=session.get("error"),
    )


# ---------------------------------------------------------------------------
# DELETE /api/cleanup/{session_id}
# ---------------------------------------------------------------------------
@router.delete("/cleanup/{session_id}", response_model=CleanupResponse)
async def cleanup(session_id: str):
    """Remove temp audio and session data.

    No-op for an in-flight session: popping it (or deleting its temp audio)
    while the pipeline thread is still running would orphan the thread's
    writes and could delete the audio mid-transcription. The pipeline cleans
    up its own temp file and the session is evicted once finished.
    """
    with _sessions_lock:
        session = _sessions.get(session_id)
        if session is not None and session.get("status") not in _FINISHED_STATUSES:
            raise HTTPException(
                status_code=409,
                detail="Session is still processing; cannot clean up yet.",
            )
        _sessions.pop(session_id, None)
    delete_temp(session_id)
    return CleanupResponse(success=True)
