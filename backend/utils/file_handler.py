import logging
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

TEMP_DIR = Path(__file__).parent.parent / "temp"


def ensure_dirs() -> None:
    """Create temp/ directory if it doesn't exist."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile, session_id: str) -> Path:
    """
    Save an uploaded audio file to temp/{session_id}.{ext}.
    Returns the path to the saved file.
    Raises HTTPException 400 if the file is not an audio file.
    """
    filename = file.filename or ""
    content_type = file.content_type or ""
    
    # Check if it's an audio MIME type or has an audio extension
    audio_extensions = (".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac")
    
    if not (content_type.startswith("audio/") or filename.lower().endswith(audio_extensions)):
        raise HTTPException(
            status_code=400,
            detail="Only audio files are accepted.",
        )

    # Extract extension or fallback to .webm if we can't determine it (e.g., from blobs)
    ext = Path(filename).suffix.lower()
    if not ext or ext not in audio_extensions:
        if "webm" in content_type:
            ext = ".webm"
        elif "mp4" in content_type:
            ext = ".m4a"
        elif "mpeg" in content_type:
            ext = ".mp3"
        elif "wav" in content_type:
            ext = ".wav"
        else:
            ext = ".webm" # default for browser recordings if no filename

    dest = TEMP_DIR / f"{session_id}{ext}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    return dest


def delete_temp(session_id: str) -> None:
    """Remove the temporary audio file for a session (if it exists)."""
    # Find any file starting with session_id in TEMP_DIR
    for path in TEMP_DIR.glob(f"{session_id}.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not delete temp file %s: %s", path, exc)


