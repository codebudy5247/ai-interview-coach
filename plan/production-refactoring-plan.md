# Production-Ready Code Refactoring Plan — Interview Coach

A full audit and refactoring plan to elevate the codebase from a working prototype to production-grade quality. Every issue found during the code review is documented below with a concrete fix.

---

## Scope of Review

| Area | Files Reviewed |
|------|---------------|
| Backend entry point | [main.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/main.py) |
| Routers | [analyze.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/routers/analyze.py), [sessions.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/routers/sessions.py) |
| Services | [feedback_service.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/services/feedback_service.py), [whisper_service.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/services/whisper_service.py), [imagekit_service.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/services/imagekit_service.py) |
| Models / DB | [schemas.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/models/schemas.py), [session_model.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/models/session_model.py), [database.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/database.py) |
| Utilities | [file_handler.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/utils/file_handler.py) |
| Tests | [test_analyze.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/tests/test_analyze.py), [test_api.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/tests/test_api.py) |
| Frontend core | [App.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/App.tsx), [main.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/main.tsx), [api.ts](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/services/api.ts) |
| Frontend pages | `UploadPage`, `ProgressPage`, `FeedbackPage`, `HistoryPage` |
| Frontend components | `AudioUploader`, `CodeSnippetInput`, `FeedbackReport`, `ProgressTracker`, `QuestionInput`, `ScoreRing` |
| Config | `requirements.txt`, `package.json`, `vite.config.ts`, `.env.example`, `.gitignore` |

---

## Summary of Issues Found

> [!IMPORTANT]
> **Critical issues** are marked with 🔴. **High-priority** issues with 🟠. **Medium** with 🟡. **Low/nice-to-have** with 🟢.

| # | Severity | Area | Issue |
|---|----------|------|-------|
| 1 | 🔴 | Backend | In-memory session store (`_sessions` dict) — all data lost on restart, unbounded memory growth, no TTL |
| 2 | 🔴 | Backend | `threading.Thread` for pipeline — no task queue, no cancellation, no concurrency limits |
| 3 | 🔴 | Backend | No structured logging — raw `print()` everywhere across all services |
| 4 | 🔴 | Backend | `@app.on_event("startup")` is deprecated in modern FastAPI — use `lifespan` context manager |
| 5 | 🔴 | Backend | No input validation/sanitization on `question` or `code_snippet` (prompt injection risk) |
| 6 | 🟠 | Backend | `load_dotenv()` called in multiple files independently (3 places) — should be centralized |
| 7 | 🟠 | Backend | No rate limiting on any endpoint |
| 8 | 🟠 | Backend | No request timeouts on external HTTP calls (ImageKit, Gemini, Ollama) |
| 9 | 🟠 | Backend | `import os` inside `_run_pipeline()` (line 100) and `import json` inside router functions |
| 10 | 🟠 | Backend | `datetime.utcnow` deprecated — use `datetime.now(UTC)` |
| 11 | 🟠 | Backend | SQLAlchemy `.get()` deprecated (sessions.py L56, L89) — use `session.get(Model, id)` |
| 12 | 🟠 | Backend | No database migrations (Alembic) — raw `create_all()` |
| 13 | 🟠 | Backend | `requirements.txt` has no pinned versions |
| 14 | 🟠 | Backend | `requests` library used synchronously in ImageKit service — should use `httpx` for async |
| 15 | 🟠 | Backend | SSL monkey-patching at module level in whisper_service — risky global side-effect |
| 16 | 🟡 | Backend | Gemini client instantiated on every call (feedback_service L171) — should be reused |
| 17 | 🟡 | Backend | CORS allows only localhost — needs env-based configuration |
| 18 | 🟡 | Backend | No pagination on `/api/sessions` — loads all sessions into memory |
| 19 | 🟡 | Backend | `imagekit_service.py` uses a bare `True` sentinel instead of a proper config object |
| 20 | 🟡 | Backend | `report` endpoint referenced in test/README but no longer exists in router code |
| 21 | 🟢 | Backend | `analyze_response.txt` sitting in backend root — stale artifact |
| 22 | 🟢 | Backend | `sessions.db` sitting in backend root — likely stale/duplicate DB file |
| 23 | 🔴 | Frontend | No global error boundary — unhandled promise rejections crash the app |
| 24 | 🟠 | Frontend | `FeedbackReport.tsx` L70 has a stray `console.log(feedback.audio_url)` |
| 25 | 🟠 | Frontend | No loading/error states for session deletion in HistoryPage |
| 26 | 🟠 | Frontend | `HistoryPage` search fires API call on every keystroke (no debounce) |
| 27 | 🟠 | Frontend | No shared Layout component — header/nav duplicated across pages |
| 28 | 🟡 | Frontend | `useAudioRecorder` catches with `any` type (L110) |
| 29 | 🟡 | Frontend | `App.css` is empty (0 bytes) — dead file |
| 30 | 🟡 | Frontend | `index.html` has no proper SEO meta tags |
| 31 | 🟡 | Frontend | No environment variable support for API base URL in production |
| 32 | 🟡 | Frontend | `ProgressTracker` step list is out of sync with actual pipeline steps (missing `uploading_audio`, `persisting`) |
| 33 | 🟢 | Tests | Tests use `requests` for live integration only — no isolated unit tests with mocks |
| 34 | 🟢 | Tests | No `conftest.py`, no pytest fixtures, no CI test runner |
| 35 | 🟢 | DevOps | No Dockerfile, no docker-compose, no CI/CD config |

---

## Proposed Changes

Changes are organized into **8 phases**, ordered by priority and dependency. Each phase can be implemented and verified independently.

---

### Phase 1 — Centralized Configuration & Logging

> Foundation work that all other phases depend on.

#### [NEW] backend/config.py

Create a centralized Pydantic `Settings` class using `pydantic-settings`:

```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    # Ollama  
    ollama_model: str = "llama3.2:3b"
    # Retry
    max_retries: int = 2
    retry_delay: float = 2.0
    # ImageKit
    imagekit_private_key: str = ""
    imagekit_public_key: str = ""
    imagekit_url_endpoint: str = ""
    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Database
    database_url: str = "sqlite:///interview_coach.db"
    # Server
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Rationale:** Eliminates all scattered `load_dotenv()` calls (fixes #6), validates config at startup, makes testing easy via dependency override.

#### [NEW] backend/logging_config.py

Replace all `print()` calls with structured logging:

```python
import logging
import sys

def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
```

**Rationale:** Fixes #3. All `print(f"[pipeline:...")` → `logger.info(...)`. Enables log aggregation, filtering, and future integration with services like Sentry.

#### [MODIFY] backend/main.py

- Replace `@app.on_event("startup")` with `lifespan` context manager (fixes #4)
- Import settings from `config.py` for CORS origins (fixes #17)
- Wire up structured logging

#### [MODIFY] All backend files

- Remove all `load_dotenv()` calls
- Remove all `print()` calls → replace with `logging.getLogger(__name__)`
- Remove all inline `import os` / `import json` from inside functions (fixes #9)

---

### Phase 2 — Backend Architecture Refactor

> Fix the two most critical architectural problems: in-memory state and uncontrolled threading.

#### [MODIFY] backend/routers/analyze.py

**Problem (fix #1, #2):** The `_sessions` dict is an unbounded in-memory store. On server restart, all in-progress sessions are lost. Background threads have no limits.

**Solution:**
1. **Replace `_sessions` dict with Redis-backed or DB-backed session state.** For a SQLite-only deployment, store pipeline state in the existing `InterviewSession` table with a `status` column.
2. **Add a `status` column to `InterviewSession`** to track pipeline state (`uploaded`, `transcribing`, `analyzing`, `persisting`, `done`, `error`).
3. **Replace `threading.Thread` with a proper `asyncio` + `ProcessPoolExecutor` pattern** or use `BackgroundTasks` from FastAPI correctly. For CPU-bound Whisper work, keep `ProcessPoolExecutor` but add a semaphore to limit concurrency:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

MAX_CONCURRENT_PIPELINES = 3
_pipeline_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PIPELINES)
_executor = ProcessPoolExecutor(max_workers=MAX_CONCURRENT_PIPELINES)
```

4. **Add session TTL:** Auto-expire in-memory SSE queues after 10 minutes via a periodic cleanup task.
5. **Keep SSE queue in-memory** (it's ephemeral by design) but persist all durable state to DB immediately.

#### [MODIFY] backend/services/feedback_service.py

- Remove all `load_dotenv()` and `os.getenv()` calls — accept a `Settings` object or use dependency injection
- **Reuse Gemini client** (fix #16): create the `genai.Client` once at module level
- Add explicit **request timeouts** (fix #8):
  ```python
  response = client.models.generate_content(..., request_options={"timeout": 60})
  ```
- Replace `callable` type hint with `Callable` from `typing` (it's technically valid but unconventional)
- Fix the duplicate `import re as _re` inside `_gemini_retry_delay` — use the top-level import

#### [MODIFY] backend/services/whisper_service.py

- Remove SSL monkey-patching (fix #15) — handle it in `config.py` or at startup only
- Accept model name from `Settings` instead of hardcoded `"base"`

#### [MODIFY] backend/services/imagekit_service.py

- Replace `requests` with `httpx` for async support (fix #14)
- Remove bare `imagekit = True` sentinel (fix #19) — use a proper config check
- Add request timeout (fix #8)
- Remove `load_dotenv()` — use `Settings`

---

### Phase 3 — Database Improvements

#### [MODIFY] backend/models/session_model.py

```diff
-from datetime import datetime
+from datetime import datetime, UTC

 class InterviewSession(Base):
     __tablename__ = "sessions"
     
     id = Column(String, primary_key=True)
     question = Column(Text, nullable=False)
     transcript = Column(Text, nullable=False)
     overall_score = Column(Integer, nullable=False)
     feedback_json = Column(Text, nullable=False)
     code_snippet = Column(Text, nullable=True)
     code_language = Column(String, nullable=True)
-    created_at = Column(DateTime, default=datetime.utcnow)
+    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
+    status = Column(String, default="uploaded", nullable=False)
+    error_message = Column(Text, nullable=True)
+    audio_url = Column(String, nullable=True)
+    imagekit_file_id = Column(String, nullable=True)
```

**Rationale:** Fixes #10 (deprecated `utcnow`). Adds `status` column for pipeline state tracking, promoting ephemeral data to durable storage.

#### [MODIFY] backend/database.py

- Use the database URL from `Settings`
- Add `autoflush=False` to session maker for safety

#### [NEW] backend/alembic/ (migration setup)

Set up Alembic for proper schema migrations instead of `create_all()` (fixes #12):

```bash
alembic init alembic
alembic revision --autogenerate -m "initial_schema"
```

#### [MODIFY] backend/routers/sessions.py

- Fix deprecated `.get()` calls (fix #11): `db.query(InterviewSession).get(id)` → `db.get(InterviewSession, id)`
- Move `import json` to top of file (fix #9)
- Add **pagination** to `/api/sessions` (fix #18):
  ```python
  @router.get("/sessions")
  def list_sessions(
      search: str = "",
      sort: str = "newest",
      page: int = Query(1, ge=1),
      limit: int = Query(20, ge=1, le=100),
  ):
  ```

---

### Phase 4 — API Hardening

#### [MODIFY] backend/main.py

- Add **rate limiting** middleware using `slowapi` (fix #7):
  ```python
  from slowapi import Limiter
  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  ```
- Add **request size limits** to prevent large file abuse
- Add **CORS env-based configuration** (fix #17)

#### [MODIFY] backend/routers/analyze.py

- Add input validation for `question` (min/max length, strip dangerous chars) (fix #5)
- Add file size limit enforcement server-side (not just client)
- Add rate limit decorator: `@limiter.limit("10/minute")`

#### [NEW] backend/middleware/

Create middleware for:
1. **Request ID injection** — attach a UUID to every request for log correlation
2. **Error handling** — global exception handler that returns structured JSON errors

#### Remove stale files (fix #21, #22)

- Delete `backend/analyze_response.txt`
- Delete `backend/sessions.db`

---

### Phase 5 — Frontend Refactoring

#### [NEW] frontend/src/components/Layout.tsx

Create a shared layout component with header/nav (fix #27):

```tsx
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-3">
        <nav className="max-w-4xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-lg font-bold text-slate-100">🎯 Interview Coach</Link>
          <Link to="/history" className="text-sm text-indigo-400">📚 History</Link>
        </nav>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  )
}
```

#### [NEW] frontend/src/components/ErrorBoundary.tsx

Add a global error boundary (fix #23):

```tsx
class ErrorBoundary extends React.Component<Props, State> {
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) return <ErrorFallback error={this.state.error} />
    return this.props.children
  }
}
```

#### [MODIFY] frontend/src/components/FeedbackReport.tsx

- Remove `console.log(feedback.audio_url)` on line 70 (fix #24)

#### [MODIFY] frontend/src/pages/HistoryPage.tsx

- Add **debounce** to search input (fix #26) — use a custom `useDebounce` hook:
  ```tsx
  const debouncedSearch = useDebounce(search, 300)
  useEffect(() => { loadSessions() }, [debouncedSearch, sort])
  ```
- Add loading/error feedback for delete operations (fix #25)

#### [MODIFY] frontend/src/components/ProgressTracker.tsx

- Update STEPS array to match actual pipeline steps — add `uploading_audio` and `persisting` (fix #32)

#### [MODIFY] frontend/src/hooks/useAudioRecorder.ts

- Replace `catch (err: any)` with `catch (err: unknown)` and proper type narrowing (fix #28)

#### [DELETE] frontend/src/App.css

Remove empty dead file (fix #29)

#### [MODIFY] frontend/src/services/api.ts

- Support configurable base URL via environment variable (fix #31):
  ```ts
  const http = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })
  ```

#### [MODIFY] frontend/index.html

Add proper SEO meta tags (fix #30):

```html
<meta name="description" content="AI-powered interview practice tool. Upload your answers, get instant feedback." />
<meta name="theme-color" content="#0f1117" />
```

---

### Phase 6 — Testing Infrastructure

#### [NEW] backend/tests/conftest.py

Set up pytest with proper fixtures:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)
```

#### [NEW] backend/tests/test_unit_feedback.py

Unit tests for `feedback_service` with mocked Gemini/Ollama calls:
- Test prompt building
- Test JSON parsing with/without markdown fences
- Test retry logic
- Test fallback from Gemini to Ollama

#### [NEW] backend/tests/test_unit_schemas.py

Validate Pydantic model serialization/deserialization.

#### [MODIFY] backend/requirements.txt

Add test dependencies with pinned versions:

```
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27    # for TestClient and async ImageKit
```

#### [MODIFY] backend/requirements.txt — Pin ALL versions (fix #13)

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.19
openai-whisper==20240930
ollama==0.4.7
google-genai==1.14.0
python-dotenv==1.0.1
certifi==2024.12.14
imageio-ffmpeg==0.5.1
sqlalchemy==2.0.36
pydantic-settings==2.7.0
httpx==0.28.1
slowapi==0.1.9
alembic==1.14.1
```

---

### Phase 7 — DevOps Readiness

#### [NEW] Dockerfile

Multi-stage Dockerfile for the backend:

```dockerfile
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### [NEW] docker-compose.yml

Full-stack dev environment:

```yaml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    volumes: ["./backend:/app"]
  frontend:
    build: ./frontend
    ports: ["5173:5173"]
    depends_on: [backend]
```

#### [NEW] .github/workflows/ci.yml

CI pipeline:
1. Lint (ruff + eslint)
2. Type-check (mypy + tsc)
3. Unit tests (pytest + vitest)
4. Build verification

#### [MODIFY] backend/main.py

Enhance `/health` endpoint to include dependency checks:

```python
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.1.0",
        "environment": settings.environment,
        "db": "connected" if check_db() else "error",
    }
```

---

### Phase 8 — Documentation Updates

#### [MODIFY] CLAUDE.md

- Update architecture section to reflect new files (`config.py`, `logging_config.py`, `middleware/`)
- Add Phase 2 pipeline architecture
- Update API endpoints table with pagination params

#### [MODIFY] README.md

- Add Docker quickstart section
- Update project structure tree
- Add environment variable documentation table
- Remove references to `reports/` directory (reports are DB-stored now)

#### [MODIFY] backend/.env.example

Add new config variables:

```env
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Redis or SQLite-only?**
> For the session state migration (Phase 2), do you want to keep it SQLite-only (simpler, but SSE polling becomes DB reads) or introduce Redis for the ephemeral session/SSE state? SQLite-only is recommended for your current scale.

> [!IMPORTANT]
> **Q2 — Alembic migrations (Phase 3)?**
> Adding Alembic will require a one-time migration of your existing DB. Are you comfortable with that, or do you prefer to keep `create_all()` for now and add Alembic later?

> [!IMPORTANT]
> **Q3 — Docker priority?**
> Is Docker/CI (Phase 7) something you need now, or should we defer it to focus on code quality first?

> [!IMPORTANT]
> **Q4 — Authentication?**
> The V2 roadmap mentions user accounts. Should we add auth-ready scaffolding (e.g., JWT middleware, user model) in this refactor, or keep it out of scope?

> [!IMPORTANT]
> **Q5 — Phase prioritization?**
> The phases are ordered by dependency, but we can skip or defer any phase. Which phases do you want to tackle first? My recommendation: **Phase 1 → Phase 2 → Phase 5 → Phase 3 → Phase 4 → Phase 6 → Phase 7 → Phase 8**.

---

## Verification Plan

### Automated Tests
- `cd backend && pytest tests/ -v --tb=short` — run all unit + integration tests
- `cd frontend && npx tsc --noEmit` — verify TypeScript types
- `cd frontend && pnpm lint` — verify ESLint passes
- `cd frontend && pnpm build` — verify production build succeeds

### Manual Verification
- Full end-to-end flow: Upload → Progress → Feedback → History
- Server restart during pipeline — verify session recovery from DB
- Concurrent sessions — verify semaphore limits work
- Browser test via the browser tool to verify UI after layout changes

### Regression Checks
- Run existing `test_analyze.py` E2E test against refactored backend
- Verify SSE stream still works through Vite proxy
- Verify session history loads from DB after server restart
