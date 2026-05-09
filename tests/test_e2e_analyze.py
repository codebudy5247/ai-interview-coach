"""
tests/test_e2e_analyze.py
--------------------------
Full end-to-end test for the interview-coach analyze pipeline.

Tests the following flow in sequence:
  1. GET  /health                     — server is reachable
  2. POST /api/analyze                — upload MP3 + question → get session_id
  3. GET  /api/status/{session_id}    — immediate status check (should be 'uploaded')
  4. GET  /api/progress/{session_id}  — consume SSE stream until done/error
  5. GET  /api/feedback/{session_id}  — validate feedback JSON structure
  6. GET  /api/report/{session_id}    — download .txt report and verify content
  7. GET  /api/status/{session_id}    — final status must be 'done'
  8. DELETE /api/cleanup/{session_id} — cleanup session

Run:
    cd /Users/ujjwal/Desktop/code/interview-coach
    python tests/test_e2e_analyze.py
"""

import json
import math
import os
import struct
import sys
import tempfile
import time
import wave
import subprocess

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = "http://localhost:8000"
TIMEOUT = 300  # seconds to wait for the full pipeline (Whisper + AI can be slow)
TEST_QUESTION = (
    "Explain what a Python decorator is and give a simple real-world example."
)

# ffmpeg lives inside the venv (symlinked by whisper_service on first import)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_BIN = os.path.join(_SCRIPT_DIR, "..", "backend", "venv", "bin")
FFMPEG = os.path.join(_VENV_BIN, "ffmpeg") if os.path.exists(
    os.path.join(_VENV_BIN, "ffmpeg")
) else "ffmpeg"

# ANSI colours
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ok(msg: str):
    print(f"  {GREEN}✅ {msg}{RESET}")

def fail(msg: str):
    print(f"  {RED}❌ {msg}{RESET}")
    sys.exit(1)

def info(msg: str):
    print(f"  {CYAN}ℹ  {msg}{RESET}")

def warn(msg: str):
    print(f"  {YELLOW}⚠  {msg}{RESET}")

def section(title: str):
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")


def generate_test_mp3(path: str) -> None:
    """
    Generate a test MP3 with real spoken content using macOS `say`.
    Falls back to a WAV→MP3 sine-wave tone if `say` is unavailable.
    """
    aiff_path = path.replace(".mp3", ".aiff")

    # Try macOS TTS first — produces actual speech Whisper can transcribe
    speech = (
        "A Python decorator is a function that wraps another function to extend "
        "its behavior without modifying the original code. For example, a timing "
        "decorator can measure how long a function takes to run. Decorators are "
        "commonly used for logging, caching, and authentication."
    )
    r = subprocess.run(["say", speech, "-o", aiff_path], capture_output=True)
    if r.returncode == 0 and os.path.exists(aiff_path):
        # Convert AIFF → MP3
        result = subprocess.run(
            [FFMPEG, "-y", "-i", aiff_path, "-q:a", "4", path],
            capture_output=True,
        )
        os.unlink(aiff_path)
        if result.returncode == 0 and os.path.exists(path):
            return

    # Fallback: sine wave (Whisper will return empty transcript — test will warn)
    samplerate, duration_sec, freq = 16000, 6, 440.0
    nsamples = samplerate * duration_sec
    wav_path = path.replace(".mp3", ".wav")
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        for i in range(nsamples):
            val = int(32767 * math.sin(2 * math.pi * freq * i / samplerate))
            wf.writeframes(struct.pack("<h", val))

    result = subprocess.run(
        [FFMPEG, "-y", "-i", wav_path, "-q:a", "9", path],
        capture_output=True,
    )
    os.unlink(wav_path)
    if result.returncode != 0 or not os.path.exists(path):
        raise RuntimeError(f"ffmpeg failed to create MP3:\n{result.stderr.decode()}")


# ---------------------------------------------------------------------------
# Test Steps
# ---------------------------------------------------------------------------

def test_health():
    section("Step 1 — Health Check")
    r = requests.get(f"{BASE_URL}/health", timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    body = r.json()
    assert body.get("status") == "ok", f"Unexpected body: {body}"
    ok(f"Server is up — {body}")


def test_upload(mp3_path: str) -> str:
    section("Step 2 — POST /api/analyze (Upload MP3 + Question)")
    info(f"MP3 path : {mp3_path}")
    info(f"MP3 size : {os.path.getsize(mp3_path)} bytes")
    info(f"Question : {TEST_QUESTION}")

    with open(mp3_path, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/api/analyze",
            data={"question": TEST_QUESTION},
            files={"audio": ("test_interview.mp3", f, "audio/mpeg")},
            timeout=30,
        )

    if r.status_code != 200:
        fail(f"Upload failed — HTTP {r.status_code}: {r.text}")

    body = r.json()
    session_id = body.get("session_id")
    if not session_id:
        fail(f"No session_id in response: {body}")

    ok(f"Upload accepted — session_id: {session_id}")
    return session_id


def test_initial_status(session_id: str):
    section("Step 3 — GET /api/status (Immediate Check)")
    r = requests.get(f"{BASE_URL}/api/status/{session_id}", timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    status = body.get("status")
    info(f"Initial status: {status}")
    assert status in ("uploaded", "transcribing"), (
        f"Expected 'uploaded' or 'transcribing', got '{status}'"
    )
    ok(f"Status is '{status}' right after upload — correct")


def test_sse_stream(session_id: str):
    section("Step 4 — GET /api/progress (SSE Stream)")
    info("Opening SSE connection — waiting for pipeline to complete...")
    info(f"Timeout: {TIMEOUT}s")

    url = f"{BASE_URL}/api/progress/{session_id}"
    events_received = []
    final_step = None
    start = time.time()

    try:
        with requests.get(url, stream=True, timeout=TIMEOUT) as r:
            if r.status_code != 200:
                fail(f"SSE endpoint returned HTTP {r.status_code}: {r.text}")

            for raw_line in r.iter_lines():
                if time.time() - start > TIMEOUT:
                    fail(f"SSE stream timed out after {TIMEOUT}s")

                if not raw_line:
                    continue

                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data:"):
                    continue

                payload = line[len("data:"):].strip()
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    warn(f"Could not parse SSE payload: {payload}")
                    continue

                step    = event.get("step", "?")
                status  = event.get("status", "?")
                message = event.get("message", "")
                elapsed = time.time() - start

                print(f"    [{elapsed:6.1f}s]  {CYAN}{step:18}{RESET}  {status:15}  {message}")
                events_received.append(event)
                final_step = step

                if step in ("done", "error"):
                    break

    except requests.exceptions.ChunkedEncodingError:
        # Stream closed by server — normal at end
        pass

    print()
    info(f"SSE stream closed after {len(events_received)} events")

    if final_step == "error":
        # Extract the last error message
        last_error = next(
            (e.get("message") for e in reversed(events_received) if e.get("step") == "error"),
            "unknown error",
        )
        fail(f"Pipeline ended in error: {last_error}")

    if final_step != "done":
        fail(f"Pipeline did not reach 'done'. Last step: {final_step}")

    # Validate expected steps were received
    received_steps = {e["step"] for e in events_received}
    expected_steps = {"transcribing", "analyzing", "saving_report", "done"}
    missing = expected_steps - received_steps
    if missing:
        warn(f"Some expected steps were not seen in SSE stream: {missing}")
    else:
        ok(f"All expected pipeline steps received: {sorted(received_steps)}")

    ok(f"SSE stream completed successfully in {time.time() - start:.1f}s")


def test_feedback(session_id: str) -> dict:
    section("Step 5 — GET /api/feedback (Validate JSON Structure)")
    r = requests.get(f"{BASE_URL}/api/feedback/{session_id}", timeout=30)

    if r.status_code == 202:
        fail("Pipeline still processing when feedback was requested — pipeline may not have finished")
    if r.status_code != 200:
        fail(f"Feedback endpoint returned HTTP {r.status_code}: {r.text}")

    feedback = r.json()

    # --- Schema validation ---
    required_keys = [
        "overall_score", "scores",
        "what_went_well", "what_was_missed",
        "improvements", "ideal_answer", "transcript",
    ]
    missing_keys = [k for k in required_keys if k not in feedback]
    if missing_keys:
        fail(f"Feedback JSON missing keys: {missing_keys}\nGot: {list(feedback.keys())}")

    ok(f"All required keys present: {required_keys}")

    # --- Score validation ---
    overall = feedback["overall_score"]
    assert isinstance(overall, int), f"overall_score should be int, got {type(overall)}"
    assert 1 <= overall <= 10, f"overall_score out of range: {overall}"
    ok(f"overall_score = {overall}/10 ✓")

    expected_dims = {"correctness", "clarity", "structure", "relevance"}
    scores = feedback.get("scores", {})
    missing_dims = expected_dims - set(scores.keys())
    if missing_dims:
        warn(f"Missing score dimensions: {missing_dims}")
    else:
        ok(f"All 4 score dimensions present: {sorted(scores.keys())}")

    for dim, val in scores.items():
        s = val.get("score")
        f_text = val.get("feedback", "")
        assert isinstance(s, int) and 1 <= s <= 10, f"{dim}.score out of range: {s}"
        assert f_text, f"{dim}.feedback is empty"
        info(f"  {dim:15}: {s}/10 — {f_text[:60]}...")

    # --- List fields ---
    for field in ("what_went_well", "what_was_missed", "improvements"):
        items = feedback.get(field, [])
        assert isinstance(items, list) and len(items) > 0, f"{field} is empty or not a list"
        ok(f"{field}: {len(items)} items")

    # --- Text fields ---
    assert feedback.get("ideal_answer"), "ideal_answer is empty"
    ok(f"ideal_answer: {feedback['ideal_answer'][:80]}...")

    assert feedback.get("transcript"), "transcript is empty"
    ok(f"transcript: {feedback['transcript'][:80]}...")

    return feedback


def test_report_download(session_id: str):
    section("Step 6 — GET /api/report (Download .txt Report)")
    r = requests.get(
        f"{BASE_URL}/api/report/{session_id}",
        timeout=30,
        allow_redirects=True,
    )

    if r.status_code != 200:
        fail(f"Report endpoint returned HTTP {r.status_code}: {r.text}")

    content_type = r.headers.get("content-type", "")
    assert "text/plain" in content_type, f"Expected text/plain, got: {content_type}"
    ok(f"Content-Type: {content_type}")

    content_disp = r.headers.get("content-disposition", "")
    assert "feedback.txt" in content_disp, f"Unexpected Content-Disposition: {content_disp}"
    ok(f"Content-Disposition: {content_disp}")

    report_text = r.text
    assert len(report_text) > 100, f"Report content too short ({len(report_text)} chars)"
    ok(f"Report content length: {len(report_text)} chars")

    # Validate expected sections
    expected_sections = [
        "INTERVIEW COACH — FEEDBACK REPORT",
        "OVERALL SCORE",
        "SCORES",
        "WHAT YOU DID WELL",
        "WHAT YOU MISSED",
        "HOW TO IMPROVE",
        "YOUR TRANSCRIPT",
        "IDEAL ANSWER",
        "Generated by Interview Coach",
    ]
    missing_sections = [s for s in expected_sections if s not in report_text]
    if missing_sections:
        fail(f"Report is missing sections: {missing_sections}")
    ok(f"All {len(expected_sections)} report sections present")

    # Print a preview
    print()
    print(f"  {CYAN}--- Report Preview (first 600 chars) ---{RESET}")
    for line in report_text[:600].splitlines():
        print(f"  {line}")
    print(f"  {CYAN}--- End Preview ---{RESET}")


def test_final_status(session_id: str):
    section("Step 7 — GET /api/status (Final Status = 'done')")
    r = requests.get(f"{BASE_URL}/api/status/{session_id}", timeout=10)
    assert r.status_code == 200
    body = r.json()
    status = body.get("status")
    info(f"Final status: {status}")
    assert status == "done", f"Expected 'done', got '{status}'"
    ok(f"Pipeline status confirmed as 'done'")


def test_cleanup(session_id: str):
    section("Step 8 — DELETE /api/cleanup (Session Cleanup)")
    r = requests.delete(f"{BASE_URL}/api/cleanup/{session_id}", timeout=10)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("success") is True, f"Unexpected response: {body}"
    ok(f"Session cleaned up successfully")

    # Verify it's actually gone
    r2 = requests.get(f"{BASE_URL}/api/status/{session_id}", timeout=10)
    assert r2.status_code == 404, (
        f"Expected 404 after cleanup, got {r2.status_code}"
    )
    ok("Session confirmed removed (404 on subsequent status call)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Interview Coach — Full E2E Test{RESET}")
    print(f"{BOLD}  Backend: {BASE_URL}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    # --- Generate test MP3 ---
    section("Setup — Generating Test MP3")
    mp3_path = os.path.join(tempfile.gettempdir(), "e2e_test_interview.mp3")
    try:
        generate_test_mp3(mp3_path)
        ok(f"Test MP3 created: {mp3_path} ({os.path.getsize(mp3_path)} bytes)")
    except Exception as e:
        fail(f"Could not create test MP3: {e}")

    # --- Run all steps ---
    test_health()
    session_id = test_upload(mp3_path)
    test_initial_status(session_id)
    test_sse_stream(session_id)
    feedback = test_feedback(session_id)
    test_report_download(session_id)
    test_final_status(session_id)
    test_cleanup(session_id)

    # --- Summary ---
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{GREEN}{BOLD}  ✅ ALL TESTS PASSED — Full pipeline working end-to-end!{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}\n")

    # Cleanup temp file
    try:
        os.unlink(mp3_path)
    except Exception:
        pass


if __name__ == "__main__":
    main()
