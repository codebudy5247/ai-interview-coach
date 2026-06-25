"""
config.py
---------
Centralized configuration. Reads environment variables once at import and
exposes typed constants so the rest of the backend doesn't sprinkle
`os.getenv` / hardcoded values across modules.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _get_list(name: str, default: list[str]) -> list[str]:
    """Parse a comma-separated env var into a list, falling back to default."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = _get_list(
    "CORS_ORIGINS",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)

# ---------------------------------------------------------------------------
# Feedback providers
# ---------------------------------------------------------------------------
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21").strip()


def _resolve_azure_endpoint() -> str:
    """Accept either AZURE_OPENAI_ENDPOINT (full URL) or AZURE_OPENAI_RESOURCE_NAME."""
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    if endpoint:
        return endpoint
    resource = os.getenv("AZURE_OPENAI_RESOURCE_NAME", "").strip()
    if resource:
        return f"https://{resource}.openai.azure.com"
    return ""


AZURE_OPENAI_ENDPOINT: str = _resolve_azure_endpoint()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()

MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "2"))

# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base").strip()

# ---------------------------------------------------------------------------
# SSE progress stream
# ---------------------------------------------------------------------------
SSE_POLL_INTERVAL: float = float(os.getenv("SSE_POLL_INTERVAL", "0.2"))
SSE_DRAIN_DELAY: float = float(os.getenv("SSE_DRAIN_DELAY", "0.1"))

# ---------------------------------------------------------------------------
# Input limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))  # 100 MB
MAX_QUESTION_LEN: int = int(os.getenv("MAX_QUESTION_LEN", "2000"))
MAX_CODE_LEN: int = int(os.getenv("MAX_CODE_LEN", "10000"))

# ---------------------------------------------------------------------------
# In-memory session store (volatile pipeline state)
# ---------------------------------------------------------------------------
SESSION_STORE_MAX: int = int(os.getenv("SESSION_STORE_MAX", "100"))
SESSION_TTL_SECONDS: float = float(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour
