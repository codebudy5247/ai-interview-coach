"""
feedback_service.py
-------------------
Generates structured interview feedback using:
  PRIMARY  → Google Gemini API (gemini-2.0-flash)
  FALLBACK → Ollama llama3.2 (local)

Each provider is retried up to MAX_RETRIES times before moving to the next.
If both fail completely, FeedbackServiceError is raised.

Environment variables (loaded from backend/.env):
  GEMINI_API_KEY   — Gemini API key. Leave blank to skip Gemini and go straight to Ollama.
  MAX_RETRIES      — Number of attempts per provider (default: 2)
  RETRY_DELAY      — Seconds between retries (default: 2)
"""

import json
import os
import re
import time

import ollama
from google import genai
from textwrap import dedent
from google.genai import types
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "2"))

GEMINI_MODEL = "gemini-3-flash-preview" # gemini-3.1-flash-lite
OLLAMA_MODEL = "llama3.2:3b"

# ---------------------------------------------------------------------------
# Scoring rubric — centralised so it's easy to tune weights / criteria
# ---------------------------------------------------------------------------
RUBRIC: dict[str, str] = {
    "correctness": "Technical accuracy and depth of the answer",
    "clarity":     "How easy the answer is to follow for a non-expert listener",
    "structure":   "Logical flow: opening, body, conclusion (STAR/PREP preferred)",
    "relevance":   "How directly the answer addresses what was actually asked",
}

# JSON schema shown to the model as a concrete example
_EXAMPLE_OUTPUT = {
    "overall_score": 7,
    "scores": {
        dim: {"score": 7, "feedback": "..."}
        for dim in RUBRIC
    },
    "what_went_well":  ["point 1", "point 2"],
    "what_was_missed": ["point 1", "point 2"],
    "improvements":    ["actionable suggestion 1", "actionable suggestion 2"],
    "ideal_answer":    "A complete model answer to this question.",
}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------
class FeedbackServiceError(Exception):
    """Raised when all providers exhaust their retries."""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def build_prompt(question: str, transcript: str) -> str:
    """
    Build the evaluation prompt used by Gemini / Ollama.

    Design choices
    --------------
    * Role + context up front — LLMs attend more strongly to early tokens.
    * Explicit rubric with per-dimension guidance keeps scores consistent.
    * JSON schema is generated programmatically so it stays in sync with RUBRIC.
    * Negative constraints ("no markdown") are placed right before the output
      request, where recency makes them most effective.
    * dedent() removes accidental indentation from the triple-quoted block.
    """
    if not question.strip():
        raise ValueError("question must not be blank")
    if not transcript.strip():
        raise ValueError("transcript must not be blank")

    rubric_block = "\n".join(
        f"  - {dim} (1-10): {desc}" for dim, desc in RUBRIC.items()
    )
    schema = json.dumps(_EXAMPLE_OUTPUT, indent=2)

    return dedent(f"""
        You are a senior software engineer conducting mock technical interviews.
        Your role is to give honest, specific, and actionable feedback.

        ## Interview Question
        {question.strip()}

        ## Candidate's Answer (transcribed from audio)
        {transcript.strip()}

        ## Evaluation Rubric
        Score each dimension from 1 (poor) to 10 (excellent):
        {rubric_block}

        ## Instructions
        - Be strict but fair; a score of 10 requires a near-perfect answer.
        - Feedback per dimension must be 1-2 concrete sentences, not generic praise.
        - `what_went_well` and `what_was_missed` should each have 2-4 bullet points.
        - `improvements` must be specific and actionable (e.g. "Mention Big-O complexity").
        - `ideal_answer` should be a complete, concise model answer (3-5 sentences).
        - `overall_score` is your holistic judgment, NOT a simple average.

        ## Output
        Return ONLY a valid JSON object. No markdown fences, no commentary.

        {schema}
    """).strip()

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
        raise ValueError(f"JSON parse error: {exc}\nRaw response:\n{raw[:500]}") from exc


# ---------------------------------------------------------------------------
# Provider: Gemini
# ---------------------------------------------------------------------------
def _call_gemini(prompt: str) -> dict:
    """
    Send the prompt to Gemini and return the parsed feedback dict.
    Raises any exception on failure (caller handles retries).
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    raw = response.text
    print(f"[feedback_service] Gemini raw response (first 200 chars): {raw[:200]}")
    return _parse_json(raw)


def _gemini_retry_delay(exc: Exception) -> float:
    """
    If the exception is a 429 rate-limit, extract the retryDelay from the
    error response and return it. Otherwise return the configured RETRY_DELAY.
    This prevents hammering the API with retries it told us to wait on.
    """
    msg = str(exc)
    # API returns 'Please retry in X.XXXs'
    import re as _re
    match = _re.search(r'retry in (\d+(?:\.\d+)?)s', msg)
    if match:
        suggested = float(match.group(1))
        print(f"[feedback_service] Rate-limited. API says retry in {suggested}s.")
        return suggested
    return RETRY_DELAY


def _is_quota_exhausted(exc: Exception) -> bool:
    """Return True if this is a per-day quota error (retrying won't help)."""
    msg = str(exc)
    return "429" in msg and "PerDay" in msg


# ---------------------------------------------------------------------------
# Provider: Ollama
# ---------------------------------------------------------------------------
def _call_ollama(prompt: str) -> dict:
    """
    Send the prompt to Ollama (llama3.2) and return the parsed feedback dict.
    Raises any exception on failure (caller handles retries).
    """
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response["message"]["content"]
    print(f"[feedback_service] Ollama raw response (first 200 chars): {raw[:200]}")
    return _parse_json(raw)


# ---------------------------------------------------------------------------
# Public API — get_feedback()
# ---------------------------------------------------------------------------
def get_feedback(question: str, transcript: str) -> dict:
    """
    Generate structured feedback for the given question + transcript.

    Provider chain:
      1. Gemini (gemini-2.0-flash) — skipped if GEMINI_API_KEY is blank
         Retried MAX_RETRIES times. On 429 rate-limit, waits the API-suggested delay.
         On per-day quota exhaustion, skips straight to Ollama.
      2. Ollama (llama3.2) — local fallback
         Retried MAX_RETRIES times before raising FeedbackServiceError.

    Returns:
        Parsed feedback dict matching the FeedbackResponse schema.

    Raises:
        FeedbackServiceError: When all providers and all retries are exhausted.
    """
    prompt = build_prompt(question, transcript)

    # --- PRIMARY: Gemini ---
    if GEMINI_API_KEY:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                print(f"[feedback_service] Gemini attempt {attempt}/{MAX_RETRIES}...")
                result = _call_gemini(prompt)
                print("[feedback_service] Gemini succeeded.")
                return result
            except Exception as exc:
                print(f"[feedback_service] Gemini attempt {attempt} failed: {exc}")
                if _is_quota_exhausted(exc):
                    print("[feedback_service] Daily quota exhausted — skipping to Ollama.")
                    break
                if attempt < MAX_RETRIES:
                    delay = _gemini_retry_delay(exc)
                    time.sleep(delay)
        print("[feedback_service] Gemini exhausted all retries. Falling back to Ollama...")
    else:
        print("[feedback_service] GEMINI_API_KEY not set — skipping Gemini, using Ollama directly.")

    # --- FALLBACK: Ollama llama3.2 ---
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[feedback_service] Ollama attempt {attempt}/{MAX_RETRIES}...")
            result = _call_ollama(prompt)
            print("[feedback_service] Ollama succeeded.")
            return result
        except Exception as exc:
            print(f"[feedback_service] Ollama attempt {attempt} failed: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    raise FeedbackServiceError(
        "Both Gemini and Ollama failed to generate feedback after all retries. "
        "Check your API key, internet connection, and that Ollama is running."
    )
