from imagekitio import ImageKit
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

public_key = os.getenv("IMAGEKIT_PUBLIC_KEY")
private_key = os.getenv("IMAGEKIT_PRIVATE_KEY")
url_endpoint = os.getenv("IMAGEKIT_URL_ENDPOINT")

if not all([private_key, url_endpoint]):
    logger.warning("ImageKit credentials not configured. Audio upload will be disabled.")
    imagekit = None
else:
    imagekit = ImageKit(
        private_key=private_key,
        base_url=url_endpoint
    )


def upload_audio(file_path: str, file_name: str) -> dict:
    """Upload an audio file to ImageKit and return the URL and file ID."""
    if not imagekit:
        raise RuntimeError("ImageKit is not configured. Check environment variables.")

    with open(file_path, "rb") as file:
        file_content = file.read()

    result = imagekit.files.upload(
        file=file_content,
        file_name=file_name,
        folder="/interview-coach/audio",
    )

    return {
        "url": result.url,
        "file_id": result.file_id,
    }


def delete_audio(file_id: str) -> bool:
    """Delete an audio file from ImageKit by its file ID."""
    if not imagekit:
        logger.warning("ImageKit is not configured. Skipping audio deletion.")
        return False

    try:
        imagekit.files.delete(file_id=file_id)
        return True
    except Exception as e:
        logger.error(f"Failed to delete audio file {file_id}: {e}")
        return False