import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException

TEMP_DIR = Path(__file__).parent.parent / "temp"


def ensure_dirs() -> None:
    """Create temp/ directory if it doesn't exist."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile, session_id: str) -> Path:
    """
    Save an uploaded MP3 file to temp/{session_id}.mp3.
    Returns the path to the saved file.
    Raises HTTPException 400 if the file is not an MP3.
    """
    # Basic MIME / extension validation
    filename = file.filename or ""
    content_type = file.content_type or ""
    if not (
        filename.lower().endswith(".mp3")
        or "audio/mpeg" in content_type
        or "audio/mp3" in content_type
    ):
        raise HTTPException(
            status_code=400,
            detail="Only MP3 audio files are accepted.",
        )

    dest = TEMP_DIR / f"{session_id}.mp3"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    return dest


def delete_temp(session_id: str) -> None:
    """Remove the temporary MP3 file for a session (if it exists)."""
    path = TEMP_DIR / f"{session_id}.mp3"
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass  # Best-effort cleanup


