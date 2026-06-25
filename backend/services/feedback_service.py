"""
feedback_service.py
-------------------
Generates structured interview feedback using:
  PRIMARY  → Azure OpenAI (chat completions, JSON mode)
  FALLBACK → Google Gemini API

Each provider is retried up to MAX_RETRIES times before moving to the next.
If both fail completely, FeedbackServiceError is raised.

Environment variables (loaded from backend/.env):
  AZURE_OPENAI_API_KEY     — Azure OpenAI key. Leave blank to skip Azure and go straight to Gemini.
  AZURE_OPENAI_ENDPOINT    — e.g. https://<resource>.openai.azure.com
  AZURE_OPENAI_DEPLOYMENT  — deployment name of the chat model
  AZURE_OPENAI_API_VERSION — API version (default: 2024-10-21)
  GEMINI_API_KEY           — Gemini API key (fallback). Leave blank to skip Gemini.
  MAX_RETRIES              — Number of attempts per provider (default: 2)
  RETRY_DELAY              — Seconds between retries (default: 2)
"""

import json
import logging
import re
import time

from openai import AzureOpenAI
from google import genai

from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_RETRIES,
    RETRY_DELAY,
)
from services.prompts import build_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy client singletons — created once on first use, reused across requests.
# Built lazily so a missing key doesn't crash at import time.
# ---------------------------------------------------------------------------
_azure_client: AzureOpenAI | None = None
_gemini_client: "genai.Client | None" = None


def _get_azure_client() -> AzureOpenAI:
    global _azure_client
    if _azure_client is None:
        logger.info("Creating Azure OpenAI client (once).")
        _azure_client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
    return _azure_client


def _get_gemini_client() -> "genai.Client":
    global _gemini_client
    if _gemini_client is None:
        logger.info("Creating Gemini client (once).")
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class FeedbackServiceError(Exception):
    """Raised when all providers exhaust their retries."""


# ---------------------------------------------------------------------------
# JSON parser — strips markdown fences if a model wraps the response anyway
# ---------------------------------------------------------------------------
def _parse_json(raw: str) -> dict:
    """
    Parse the model response as JSON.
    Handles ```json ... ``` fences that some models add despite the instruction.
    Raises ValueError if parsing fails.
    """
    text = raw.strip()

    # Strip optional ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON parse error: {exc}\nRaw response:\n{raw[:500]}"
        ) from exc


# ---------------------------------------------------------------------------
# Provider: Gemini
# ---------------------------------------------------------------------------
def _call_gemini(prompt: str) -> dict:
    """
    Send the prompt to Gemini and return the parsed feedback dict.
    Raises any exception on failure (caller handles retries).
    """
    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    raw = response.text
    logger.debug("Gemini raw response (first 200 chars): %s", raw[:200])
    return _parse_json(raw)


def _gemini_retry_delay(exc: Exception) -> float:
    """
    If the exception is a 429 rate-limit, extract the retryDelay from the
    error response and return it. Otherwise return the configured RETRY_DELAY.
    This prevents hammering the API with retries it told us to wait on.
    """
    # API returns 'Please retry in X.XXXs'
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc))
    if match:
        suggested = float(match.group(1))
        logger.info("Rate-limited. API says retry in %ss.", suggested)
        return suggested
    return RETRY_DELAY


def _is_quota_exhausted(exc: Exception) -> bool:
    """Return True if this is a per-day quota error (retrying won't help)."""
    msg = str(exc)
    return "429" in msg and "PerDay" in msg


# ---------------------------------------------------------------------------
# Provider: Azure OpenAI
# ---------------------------------------------------------------------------
def _call_azure(prompt: str) -> dict:
    """
    Send the prompt to Azure OpenAI (chat completions, JSON mode) and return
    the parsed feedback dict. Raises any exception on failure (caller handles retries).
    """
    client = _get_azure_client()
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    logger.debug("Azure raw response (first 200 chars): %s", raw[:200])
    return _parse_json(raw)


def _azure_retry_delay(exc: Exception) -> float:
    """
    On a 429 rate-limit, honor the API-suggested wait. Azure returns the hint
    either as a 'retry-after' header or 'Try again in X seconds' in the message.
    Falls back to the configured RETRY_DELAY otherwise.
    """
    # openai.RateLimitError exposes the response headers, including retry-after
    retry_after = getattr(getattr(exc, "response", None), "headers", {})
    if retry_after:
        val = retry_after.get("retry-after")
        if val:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    match = re.search(r"(?:retry|try again) in (\d+(?:\.\d+)?)\s*s", str(exc), re.IGNORECASE)
    if match:
        return float(match.group(1))
    return RETRY_DELAY


# ---------------------------------------------------------------------------
# Public API — get_feedback()
# ---------------------------------------------------------------------------
def get_feedback(
    question: str,
    transcript: str,
    code_snippet: str | None = None,
    code_language: str | None = None,
    on_status: callable = None,
) -> dict:
    """
    Generate structured feedback for the given question + transcript.

    Provider chain:
      1. Azure OpenAI — skipped if AZURE_OPENAI_API_KEY is blank.
         Retried MAX_RETRIES times. On 429 rate-limit, waits the API-suggested delay.
      2. Gemini — fallback. Skipped if GEMINI_API_KEY is blank.
         Retried MAX_RETRIES times before raising FeedbackServiceError.

    Args:
        question: The interview question text.
        transcript: The transcribed audio text.
        on_status: Optional callback for status updates. Called with (provider, attempt, status, message).

    Returns:
        Parsed feedback dict matching the FeedbackResponse schema.

    Raises:
        FeedbackServiceError: When all providers and all retries are exhausted.
    """
    prompt = build_prompt(question, transcript, code_snippet, code_language)

    # --- PRIMARY: Azure OpenAI ---
    if AZURE_OPENAI_API_KEY:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("Azure attempt %s/%s...", attempt, MAX_RETRIES)
                if on_status:
                    on_status(
                        "azure",
                        attempt,
                        "in_progress",
                        f"Analyzing with Azure OpenAI (attempt {attempt})...",
                    )
                result = _call_azure(prompt)
                logger.info("Azure succeeded.")
                if on_status:
                    on_status(
                        "azure", attempt, "done", "Feedback generated via Azure OpenAI"
                    )
                return result
            except Exception as exc:
                logger.warning("Azure attempt %s failed: %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    delay = _azure_retry_delay(exc)
                    if on_status:
                        on_status(
                            "azure",
                            attempt,
                            "retrying",
                            f"Azure failed. Retrying in {delay}s...",
                        )
                    time.sleep(delay)
        logger.info("Azure exhausted all retries. Falling back to Gemini...")
        if on_status:
            on_status(
                "azure",
                MAX_RETRIES,
                "fallback",
                "Azure exhausted retries. Falling back to Gemini...",
            )
    else:
        logger.info("AZURE_OPENAI_API_KEY not set — skipping Azure, using Gemini directly.")
        if on_status:
            on_status(
                "gemini",
                1,
                "in_progress",
                "Azure not configured. Using Gemini directly...",
            )

    # --- FALLBACK: Gemini ---
    if not GEMINI_API_KEY:
        raise FeedbackServiceError(
            "Azure OpenAI failed (or is not configured) and GEMINI_API_KEY is not set. "
            "Configure at least one provider in backend/.env."
        )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Gemini attempt %s/%s...", attempt, MAX_RETRIES)
            if on_status:
                on_status(
                    "gemini",
                    attempt,
                    "in_progress",
                    f"Analyzing with Gemini (attempt {attempt})...",
                )
            result = _call_gemini(prompt)
            logger.info("Gemini succeeded.")
            if on_status:
                on_status("gemini", attempt, "done", "Feedback generated via Gemini")
            return result
        except Exception as exc:
            logger.warning("Gemini attempt %s failed: %s", attempt, exc)
            if _is_quota_exhausted(exc):
                logger.info("Daily quota exhausted — no providers left.")
                if on_status:
                    on_status(
                        "gemini",
                        attempt,
                        "quota_exhausted",
                        "Gemini daily quota exhausted.",
                    )
                break
            if attempt < MAX_RETRIES:
                delay = _gemini_retry_delay(exc)
                if on_status:
                    on_status(
                        "gemini",
                        attempt,
                        "retrying",
                        f"Gemini failed. Retrying in {delay}s...",
                    )
                time.sleep(delay)

    raise FeedbackServiceError(
        "Both Azure OpenAI and Gemini failed to generate feedback after all retries. "
        "Check your API keys and internet connection."
    )
