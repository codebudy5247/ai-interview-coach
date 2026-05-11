from dotenv import load_dotenv
import os
import logging
import base64
import requests

load_dotenv()

logger = logging.getLogger(__name__)

public_key = os.getenv("IMAGEKIT_PUBLIC_KEY")
private_key = os.getenv("IMAGEKIT_PRIVATE_KEY")
url_endpoint = os.getenv("IMAGEKIT_URL_ENDPOINT")

# API endpoint for uploads
API_BASE_URL = "https://api.imagekit.io/v1"

if not all([private_key, url_endpoint]):
    logger.warning("ImageKit credentials not configured. Audio upload will be disabled.")
    imagekit = None
else:
    imagekit = True  # Mark as configured


def _get_auth_header() -> str:
    """Generate Basic auth header from private key."""
    auth_string = f"{private_key}:"
    encoded = base64.b64encode(auth_string.encode()).decode()
    return f"Basic {encoded}"


def upload_audio(file_path: str, file_name: str) -> dict:
    """Upload an audio file to ImageKit and return the URL and file ID."""
    if not imagekit:
        raise RuntimeError("ImageKit is not configured. Check environment variables.")

    with open(file_path, "rb") as file:
        file_content = file.read()

    files = {"file": (file_name, file_content, "audio/mpeg")}
    data = {"fileName": file_name, "folder": "/interview-coach/audio"}

    response = requests.post(
        f"{API_BASE_URL}/files/upload",
        files=files,
        data=data,
        headers={"Authorization": _get_auth_header()}
    )

    if response.status_code != 200:
        logger.error(f"ImageKit upload failed: {response.status_code} - {response.text}")
        response.raise_for_status()

    result = response.json()
    return {
        "url": result["url"],
        "file_id": result["fileId"],
    }


def delete_audio(file_id: str) -> bool:
    """Delete an audio file from ImageKit by its file ID."""
    if not imagekit:
        logger.warning("ImageKit is not configured. Skipping audio deletion.")
        return False

    try:
        response = requests.delete(
            f"{API_BASE_URL}/files/{file_id}",
            headers={"Authorization": _get_auth_header()}
        )
        return response.status_code == 204
    except Exception as e:
        logger.error(f"Failed to delete audio file {file_id}: {e}")
        return False