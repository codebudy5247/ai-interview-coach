"""
whisper_service.py
------------------
Transcribes an MP3 file to text using OpenAI Whisper running locally.

Model choice guide for M1 8GB:
  "tiny"  → fastest (~30s), less accurate
  "base"  → recommended balance (~1 min)  ✅ default
  "small" → more accurate (~2 min), slower
"""

import os
import ssl
import certifi
import imageio_ffmpeg
import whisper

# ---------------------------------------------------------------------------
# macOS SSL fix
# Python on macOS often ships without system CA certs. This patches the
# default SSL context to use certifi's trusted bundle so Whisper can
# download model weights over HTTPS without certificate errors.
# ---------------------------------------------------------------------------
ssl._create_default_https_context = lambda: ssl.create_default_context(
    cafile=certifi.where()
)

# ---------------------------------------------------------------------------
# FFmpeg fix
# Whisper shells out to `ffmpeg` by name. imageio-ffmpeg bundles a static
# FFmpeg binary but names it with a version suffix (e.g. ffmpeg-macos-aarch64-v7.1).
# We create a `ffmpeg` symlink in the venv's bin/ directory (which is always
# on PATH when the venv is active) so Whisper can find it.
# This is safe to re-run — it's a no-op if the symlink already exists.
# ---------------------------------------------------------------------------
def _ensure_ffmpeg_symlink() -> None:
    import sys
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    link = os.path.join(os.path.dirname(sys.executable), "ffmpeg")
    if not os.path.exists(link):
        os.symlink(exe, link)
        print(f"[whisper_service] Created ffmpeg symlink: {link}")
    else:
        print(f"[whisper_service] ffmpeg already available at: {link}")

_ensure_ffmpeg_symlink()

# Load the model once at module level so it isn't reloaded on every request.
# Change "base" to "tiny" or "small" as needed.
_WHISPER_MODEL_NAME = "base"
_model: whisper.Whisper | None = None


def _get_model() -> whisper.Whisper:
    """Lazy-load and cache the Whisper model."""
    global _model
    if _model is None:
        print(f"[whisper_service] Loading Whisper model: {_WHISPER_MODEL_NAME}")
        _model = whisper.load_model(_WHISPER_MODEL_NAME)
        print("[whisper_service] Whisper model loaded.")
    return _model


def transcribe(mp3_path: str) -> str:
    """
    Transcribe the audio file at `mp3_path` and return the transcript string.

    Args:
        mp3_path: Absolute path to the MP3 file.

    Returns:
        The full transcript text.

    Raises:
        RuntimeError: If Whisper fails to transcribe the file.
    """
    try:
        model = _get_model()
        print(f"[whisper_service] Transcribing: {mp3_path}")
        result = model.transcribe(mp3_path, fp16=False)  # fp16=False for CPU/M1 safety
        transcript = result.get("text", "").strip()
        print(f"[whisper_service] Done. Transcript length: {len(transcript)} chars")
        return transcript
    except Exception as exc:
        raise RuntimeError(f"Whisper transcription failed: {exc}") from exc
