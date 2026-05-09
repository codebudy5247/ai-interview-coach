# ⚡ Optimization Review — Interview Coach Backend

> **Reviewed:** 2026-05-09  
> **Scope:** All backend files — `routers/`, `services/`, `utils/`, `models/`, `main.py`

## Severity Legend

| Symbol | Severity | Meaning |
|--------|----------|---------|
| 🔴 | **Critical** | Will crash or cause data loss |
| 🟠 | **High** | Significant performance / correctness issue |
| 🟡 | **Medium** | Suboptimal but workable |
| 🟢 | **Low** | Polish / minor improvement |

---

## Summary Table

| # | File | Issue | Severity |
|---|------|-------|----------|
| 1 | `routers/analyze.py` | `await time.sleep()` crashes SSE generator | 🔴 Critical |
| 2 | `routers/analyze.py` | `_sessions` dict never expires → memory leak | 🔴 Critical |
| 3 | `routers/analyze.py` | Unbounded `queue.Queue` fills if client disconnects | 🔴 Critical |
| 4 | `services/whisper_service.py` | Whisper model reloaded per uvicorn worker process | 🟠 High |
| 5 | `utils/file_handler.py` | Blocking `shutil.copyfileobj` called inside `async def` | 🟠 High |
| 6 | `routers/analyze.py` | Busy-wait SSE poll at 200ms intervals | 🟠 High |
| 7 | `services/feedback_service.py` | Gemini client re-instantiated on every call / retry | 🟠 High |
| 8 | `services/feedback_service.py` | `re` double-imported inside a function | 🟡 Medium |
| 9 | `utils/file_handler.py` | `datetime.now()` — no timezone, ambiguous on servers | 🟡 Medium |
| 10 | `main.py` | `@app.on_event("startup")` is deprecated since FastAPI 0.93 | 🟡 Medium |
| 11 | `requirements.txt` | All dependencies unpinned | 🟡 Medium |
| 12 | `routers/analyze.py` | No disconnect cleanup in SSE generator + unused variable | 🟡 Medium |
| 13 | `utils/file_handler.py` | `except Exception: pass` swallows all errors silently | 🟢 Low |
| 14 | `routers/analyze.py` | Inconsistent session access pattern in `_emit_sse` | 🟢 Low |
| 15 | `services/whisper_service.py` | `fp16=False` hardcoded, not device-aware | 🟢 Low |

---

## 🔴 Critical Issues

### 1. `await time.sleep()` — Runtime Crash in SSE Generator

**File:** `routers/analyze.py:221`

`time` is the synchronous stdlib module — it has no coroutine. This raises a `TypeError` the moment the SSE generator hits the pipeline-done branch, silently killing the stream.

```python
# ❌ Broken
await time.sleep(0.5)

# ✅ Fix
await asyncio.sleep(0.5)
```

---

### 2. `_sessions` Dict Never Expires — Memory Leak

**File:** `routers/analyze.py`

`_sessions` grows indefinitely. The `DELETE /api/cleanup` endpoint only removes a session if the *client* explicitly calls it — which the frontend currently does not. On a long-running server this leaks memory for every session ever created.

**Fix:** Store a `created_at` timestamp per session and run a periodic background sweep:

```python
import time as _time

SESSION_TTL_SECONDS = 3600  # 1 hour

async def _cleanup_expired_sessions():
    while True:
        now = _time.monotonic()
        expired = [
            sid for sid, s in list(_sessions.items())
            if now - s.get("created_at", now) > SESSION_TTL_SECONDS
        ]
        for sid in expired:
            _sessions.pop(sid, None)
        await asyncio.sleep(300)  # sweep every 5 minutes

# In lifespan / startup:
asyncio.create_task(_cleanup_expired_sessions())
```

And when creating a session:
```python
_sessions[session_id] = {
    ...
    "created_at": _time.monotonic(),
}
```

---

### 3. Unbounded `queue.Queue` Fills on Client Disconnect

**File:** `routers/analyze.py` — `_emit_sse()` + SSE generator

If the frontend disconnects mid-stream, the async generator is cancelled — but the background pipeline thread keeps calling `_emit_sse()`, continuously inserting into the queue with no consumer. The queue grows without bound until the session is cleaned up.

**Fix:** Cap the queue size and drop events silently when full:

```python
# On session creation
"events": queue.Queue(maxsize=50),

# In _emit_sse()
try:
    session["events"].put_nowait(event)
except queue.Full:
    pass  # consumer is gone, discard safely
```

---

## 🟠 High — Performance Issues

### 4. Whisper Model Reloaded Per Worker Process

**File:** `services/whisper_service.py`

The `_model` global is per-process. Running `uvicorn --workers 2` spawns 2 separate processes, each loading the Whisper "base" model (~400MB RAM each). On an M1 8GB this can exhaust memory quickly.

**Fix:** Always run with a single worker (`uvicorn main:app --workers 1`). Additionally, eagerly warm the model at startup so the first real request isn't slow:

```python
# main.py startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _get_model)  # warm Whisper
    yield
```

---

### 5. Blocking I/O on the Event Loop — `save_upload()`

**File:** `utils/file_handler.py`

```python
# ❌ Synchronous I/O inside an async function — blocks the event loop
async def save_upload(file: UploadFile, session_id: str) -> Path:
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
```

`shutil.copyfileobj` is synchronous. During the file write, FastAPI cannot handle any other incoming requests.

**Fix:** Offload to a thread pool executor:

```python
import asyncio

async def save_upload(file: UploadFile, session_id: str) -> Path:
    dest = TEMP_DIR / f"{session_id}.mp3"
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _write_file, file.file, dest)
    return dest

def _write_file(src, dest: Path) -> None:
    with dest.open("wb") as out:
        shutil.copyfileobj(src, out)
```

---

### 6. Busy-Wait SSE Poll at 200ms

**File:** `routers/analyze.py` — `event_generator()`

```python
# ❌ Wakes up 5 times/second per active SSE client, even when idle
while True:
    try:
        event = events_queue.get_nowait()
    except queue.Empty:
        pass
    await asyncio.sleep(0.2)
```

With multiple concurrent sessions this wastes CPU and creates unnecessary event loop pressure.

**Fix:** Replace `queue.Queue` with `asyncio.Queue` so the generator can truly `await` an event instead of polling:

```python
# Session creation
_event_loop = asyncio.get_event_loop()  # store at startup
"events": asyncio.Queue(),

# _emit_sse — called from a background thread, must be thread-safe
asyncio.run_coroutine_threadsafe(
    session["events"].put(event),
    _event_loop,
)

# SSE generator — zero CPU when idle
event = await session["events"].get()  # blocks until an event arrives
yield f"data: {event.model_dump_json()}\n\n"
if event.step in ("done", "error"):
    break
```

---

### 7. Gemini Client Re-instantiated on Every Call

**File:** `services/feedback_service.py` — `_call_gemini()`

```python
# ❌ New client (and HTTP connection pool) on every call / retry
def _call_gemini(prompt: str) -> dict:
    client = genai.Client(api_key=GEMINI_API_KEY)
```

**Fix:** Module-level singleton:

```python
_gemini_client: genai.Client | None = None

def _get_gemini_client() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client

def _call_gemini(prompt: str) -> dict:
    client = _get_gemini_client()
    response = client.models.generate_content(...)
```

---

## 🟡 Medium — Code Quality / Correctness

### 8. `re` Double-Imported Inside a Function

**File:** `services/feedback_service.py:173`

```python
import re          # ✅ already imported at module level (line 19)
...
def _gemini_retry_delay(exc: Exception) -> float:
    import re as _re   # ❌ redundant — runs on every retry
    match = _re.search(...)
```

**Fix:** Remove the function-level import and use the top-level `re` directly.

---

### 9. `datetime.now()` — No Timezone

**File:** `utils/file_handler.py` — `format_feedback_txt()`

```python
# ❌ Returns server local time — ambiguous and inconsistent
now = datetime.now()
```

**Fix:**
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
date_str = now.strftime("%d %b %Y (UTC)")
```

---

### 10. `@app.on_event("startup")` is Deprecated

**File:** `main.py:30`

`on_event` has been deprecated since FastAPI 0.93. It still works but will be removed in a future version.

**Fix:** Use the modern `lifespan` context manager:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    yield  # app runs here

app = FastAPI(lifespan=lifespan, title="Interview Coach API", ...)
```

---

### 11. All Dependencies Unpinned

**File:** `requirements.txt`

All packages are listed without version pins. A breaking upstream release will silently break the project on the next fresh install.

**Fix:** Pin after verifying your current working environment:
```bash
pip freeze > requirements.txt
```

Or pin manually, e.g.:
```
fastapi==0.115.9
uvicorn[standard]==0.34.0
openai-whisper==20240930
google-genai==1.14.0
ollama==0.4.7
python-dotenv==1.1.0
certifi==2025.4.26
imageio-ffmpeg==0.5.1
python-multipart==0.0.20
```

---

### 12. SSE Generator — No Disconnect Cleanup + Unused Variable

**File:** `routers/analyze.py` — `event_generator()`

- `last_event_id` is assigned but never used (and never sent in the SSE `id:` field).
- If the client disconnects, the generator is cancelled with no cleanup — the queue keeps filling.

**Fix:**
```python
async def event_generator():
    try:
        while True:
            # ... yield events ...
    finally:
        # Drain queue so the pipeline thread doesn't block on a full queue
        while not events_queue.empty():
            try:
                events_queue.get_nowait()
            except queue.Empty:
                break
```

---

## 🟢 Low — Minor Polish

### 13. `delete_temp` Silently Swallows All Exceptions

**File:** `utils/file_handler.py`

```python
except Exception:
    pass  # Best-effort cleanup — makes debugging impossible
```

**Fix:** At minimum, log the error:
```python
except Exception as exc:
    print(f"[file_handler] Warning: could not delete temp file for {session_id}: {exc}")
```

---

### 14. Inconsistent Session Access in `_emit_sse`

**File:** `routers/analyze.py`

`_emit_sse()` accesses `_sessions.get(session_id)` directly (bypassing `get_session()`), while all endpoint handlers use `get_session()`. This is intentionally correct (fire-and-forget shouldn't raise 404), but should have a comment explaining why:

```python
def _emit_sse(session_id: str, step: str, status: str, message: str) -> None:
    # Use .get() directly (not get_session()) — _emit_sse is fire-and-forget;
    # silently skipping a missing session is safer than raising mid-pipeline.
    session = _sessions.get(session_id)
    ...
```

---

### 15. `fp16=False` Hardcoded — Not Device-Aware

**File:** `services/whisper_service.py:80`

```python
result = model.transcribe(mp3_path, fp16=False)  # fp16=False for CPU/M1 safety
```

Correct for M1/CPU, but if this ever runs on a CUDA GPU, `fp16=True` gives a significant speedup.

**Fix:**
```python
import torch
fp16 = torch.cuda.is_available()
result = model.transcribe(mp3_path, fp16=fp16)
```
