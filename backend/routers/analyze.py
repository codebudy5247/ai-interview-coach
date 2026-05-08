import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

from models.schemas import AnalyzeResponse, CleanupResponse
from utils.file_handler import save_upload, delete_temp, get_report_path

router = APIRouter(prefix="/api", tags=["analyze"])

# In-memory store for pipeline results (Phase 2 will populate this)
# Key: session_id  Value: dict with "feedback", "transcript", "status", "events"
_sessions: dict[str, dict] = {}


def get_session(session_id: str) -> dict:
    """Retrieve a session or raise 404."""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


# ---------------------------------------------------------------------------
# POST /api/analyze
# Accept MP3 + question → save to temp/ → return session_id
# (AI pipeline will be connected in Phase 2)
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    question: str = Form(...),
    audio: UploadFile = File(...),
):
    """
    Step 1 of the pipeline:
    - Validate and save the uploaded MP3 file to temp/
    - Generate a unique session_id
    - Register the session in the in-memory store
    - Return session_id to the frontend
    """
    session_id = str(uuid.uuid4())

    # Save MP3 to temp/{session_id}.mp3
    mp3_path = await save_upload(audio, session_id)

    # Register session
    _sessions[session_id] = {
        "question": question,
        "mp3_path": str(mp3_path),
        "status": "uploaded",
        "feedback": None,
        "transcript": None,
        "events": [],       # SSE event history (Phase 3)
    }

    return AnalyzeResponse(session_id=session_id)


# ---------------------------------------------------------------------------
# GET /api/feedback/{session_id}
# Return stored feedback JSON (Phase 2 will fill this in)
# ---------------------------------------------------------------------------
@router.get("/feedback/{session_id}")
async def get_feedback(session_id: str):
    session = get_session(session_id)
    if session["feedback"] is None:
        raise HTTPException(status_code=202, detail="Feedback not ready yet.")
    return session["feedback"]


# ---------------------------------------------------------------------------
# GET /api/report/{session_id}
# Serve the .txt report as a file download (Phase 4)
# ---------------------------------------------------------------------------
@router.get("/report/{session_id}")
async def download_report(session_id: str):
    path = get_report_path(session_id)
    return FileResponse(
        path=str(path),
        media_type="text/plain",
        filename=f"{session_id[:8]}_feedback.txt",
    )


# ---------------------------------------------------------------------------
# DELETE /api/cleanup/{session_id}
# Remove temp MP3 and session data
# ---------------------------------------------------------------------------
@router.delete("/cleanup/{session_id}", response_model=CleanupResponse)
async def cleanup(session_id: str):
    delete_temp(session_id)
    _sessions.pop(session_id, None)
    return CleanupResponse(success=True)
