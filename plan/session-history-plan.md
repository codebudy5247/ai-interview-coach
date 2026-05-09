# 📚 Session History — Implementation Plan

> **Goal:** Persist completed interview feedback sessions to a database so users can browse, search, and review past feedback at any time — even after a server restart.

---

## Current State

- Sessions live **only in-memory** (`_sessions` dict in `routers/analyze.py`) and are lost on server restart.
- Feedback is also saved as `.txt` report files in `reports/`, but there's no API to list or browse them.
- The frontend has 3 pages: Upload → Progress → Feedback (single-session flow, no history view).

---

## User Review Required

> **Database choice: SQLite + SQLAlchemy**
> SQLite is zero-config, file-based, and perfect for a local dev tool. No Docker, no server, no credentials. The DB file lives at `backend/interview_coach.db`. If you foresee needing Postgres later, SQLAlchemy makes switching trivial. Please confirm this is acceptable.

> **Auto-save vs Manual save**
> The plan auto-saves every completed session to the DB at the end of the pipeline (no user action needed). If you'd prefer a manual "Save to History" button instead, let me know.

---

## Open Questions

1. **Pagination**: Should the history page paginate (e.g., 20 per page) or load all sessions at once? For a local tool, loading all is fine initially. Yes, we can load all sessions at once. 
2. **Delete sessions**: Should users be able to delete individual sessions from history? (Plan assumes yes.) Yes, we should be able to delete sessions. 
3. **Search/filter**: Filter by question text and sort by date — is that sufficient, or do you also want filter-by-score-range? No extra filters needed. 

---

## Proposed Changes

### Backend — Database Layer

#### [NEW] `backend/database.py`

New module for SQLAlchemy setup:

```python
# SQLite database setup using SQLAlchemy
# DB file: backend/interview_coach.db

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_PATH = Path(__file__).parent / "interview_coach.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI dependency — yields a DB session, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(bind=engine)
```

---

#### [NEW] `backend/models/session_model.py`

SQLAlchemy ORM model for persisted sessions:

```python
class InterviewSession(Base):
    __tablename__ = "sessions"

    id            = Column(String, primary_key=True)          # UUID session_id
    question      = Column(Text, nullable=False)
    transcript    = Column(Text, nullable=False)
    overall_score = Column(Integer, nullable=False)
    feedback_json = Column(Text, nullable=False)              # Full feedback as JSON string
    created_at    = Column(DateTime, default=datetime.utcnow)
```

- `feedback_json` stores the entire feedback dict as a JSON string (simple, avoids complex relational schema for scores).
- `created_at` enables sort-by-date.

---

#### [MODIFY] `backend/models/schemas.py`

Add new Pydantic response models:

```python
class SessionSummary(BaseModel):
    """Lightweight session info for the history list."""
    id: str
    question: str                # truncated for display
    overall_score: int
    created_at: str              # ISO 8601 datetime string

class SessionDetail(BaseModel):
    """Full session data for the detail view."""
    id: str
    question: str
    transcript: str
    overall_score: int
    feedback: FeedbackResponse   # reuse existing model
    created_at: str

class SessionListResponse(BaseModel):
    sessions: List[SessionSummary]
    total: int
```

---

#### [MODIFY] `backend/routers/analyze.py`

Modify `_run_pipeline()` to auto-save the session to the DB after the pipeline completes successfully:

```python
# After step 3 (saving .txt report), add:
# --- Step 3b: Persist to database ---
from database import SessionLocal
from models.session_model import InterviewSession
import json

db = SessionLocal()
try:
    db_session = InterviewSession(
        id=session_id,
        question=question,
        transcript=transcript,
        overall_score=feedback["overall_score"],
        feedback_json=json.dumps(feedback),
    )
    db.add(db_session)
    db.commit()
finally:
    db.close()
```

---

#### [NEW] `backend/routers/sessions.py`

New router for session history CRUD:

| Method   | Endpoint                   | Description                          |
|----------|----------------------------|--------------------------------------|
| `GET`    | `/api/sessions`            | List all saved sessions (summary)    |
| `GET`    | `/api/sessions/{id}`       | Get full session detail + feedback   |
| `DELETE` | `/api/sessions/{id}`       | Delete a session from history        |

```python
router = APIRouter(prefix="/api", tags=["sessions"])

@router.get("/sessions")
def list_sessions(
    search: str = "",           # filter by question text
    sort: str = "newest",       # newest | oldest | highest | lowest
    db: Session = Depends(get_db),
):
    query = db.query(InterviewSession)
    if search:
        query = query.filter(InterviewSession.question.ilike(f"%{search}%"))
    # apply sort ...
    sessions = query.all()
    return SessionListResponse(
        sessions=[SessionSummary(...) for s in sessions],
        total=len(sessions),
    )

@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return SessionDetail(...)

@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    db.delete(session)
    db.commit()
    # Also delete the .txt report file if it exists
    return {"success": True}
```

---

#### [MODIFY] `backend/main.py`

- Import and register the new `sessions` router.
- Call `init_db()` on startup to create tables.

```diff
 from routers.analyze import router as analyze_router
+from routers.sessions import router as sessions_router
+from database import init_db

 @app.on_event("startup")
 async def startup_event():
     ensure_dirs()
+    init_db()

 app.include_router(analyze_router)
+app.include_router(sessions_router)
```

---

#### [MODIFY] `backend/requirements.txt`

```diff
+sqlalchemy
```

---

### Frontend — History Page & Navigation

#### [NEW] `frontend/src/pages/HistoryPage.tsx`

New page that displays a list of all past sessions:

**Features:**
- Search bar to filter by question text
- Sort dropdown (Newest / Oldest / Highest Score / Lowest Score)
- Session cards showing: question (truncated), overall score (with color), date
- Click a card → navigates to `/feedback/{sessionId}` (reuses existing FeedbackPage)
- Delete button on each card (with confirmation)
- Empty state when no sessions exist

**UI Wireframe:**
```
┌──────────────────────────────────────────┐
│  📚 Session History                       │
│                                          │
│  🔍 [Search questions...        ]        │
│  Sort: [Newest ▼]                        │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ "Explain how closures work..."     │  │
│  │ Score: 7/10  •  09 May 2026        │  │
│  │                        [🗑️] [View] │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │ "What is the difference between..."│  │
│  │ Score: 8/10  •  08 May 2026        │  │
│  │                        [🗑️] [View] │  │
│  └────────────────────────────────────┘  │
│                                          │
│  [🎯 New Practice Session]               │
└──────────────────────────────────────────┘
```

---

#### [MODIFY] `frontend/src/services/api.ts`

Add new API functions:

```typescript
export async function getSessions(
  search?: string,
  sort?: string,
): Promise<{ sessions: SessionSummary[]; total: number }> {
  const params = new URLSearchParams()
  if (search) params.set('search', search)
  if (sort) params.set('sort', sort)
  const { data } = await http.get(`/sessions?${params}`)
  return data
}

export async function getSessionDetail(sessionId: string) {
  const { data } = await http.get(`/sessions/${sessionId}`)
  return data
}

export async function deleteSession(sessionId: string): Promise<void> {
  await http.delete(`/sessions/${sessionId}`)
}
```

---

#### [MODIFY] `frontend/src/types/api.ts`

Add `SessionSummary` and `SessionListResponse` types:

```typescript
export interface SessionSummary {
  id: string
  question: string
  overall_score: number
  created_at: string
}

export interface SessionListResponse {
  sessions: SessionSummary[]
  total: number
}
```

---

#### [MODIFY] `frontend/src/App.tsx`

Add the history route and navigation:

```diff
+import HistoryPage from './pages/HistoryPage'

 <Routes>
   <Route path="/" element={<UploadPage />} />
+  <Route path="/history" element={<HistoryPage />} />
   <Route path="/progress/:sessionId" element={<ProgressPage />} />
   <Route path="/feedback/:sessionId" element={<FeedbackPage />} />
 </Routes>
```

---

#### [MODIFY] `frontend/src/pages/UploadPage.tsx`

Add a "📚 View History" link/button in the header area that navigates to `/history`.

---

#### [MODIFY] `frontend/src/pages/FeedbackPage.tsx`

- Modify to also support loading session data from the DB endpoint (`/api/sessions/{id}`) when accessed from history (the session may no longer be in the in-memory store).
- Add a "📚 View History" button alongside the existing action buttons.

---

## File Summary

| Action   | File                                  | Description                                      |
|----------|---------------------------------------|--------------------------------------------------|
| **NEW**  | `backend/database.py`                 | SQLAlchemy engine, session factory, `init_db()`   |
| **NEW**  | `backend/models/session_model.py`     | `InterviewSession` ORM model                      |
| **NEW**  | `backend/routers/sessions.py`         | `/api/sessions` CRUD endpoints                    |
| **NEW**  | `frontend/src/pages/HistoryPage.tsx`  | Session history list page                         |
| MODIFY   | `backend/main.py`                     | Register sessions router, call `init_db()`        |
| MODIFY   | `backend/routers/analyze.py`          | Auto-save session to DB after pipeline completes  |
| MODIFY   | `backend/models/schemas.py`           | Add `SessionSummary`, `SessionDetail` schemas     |
| MODIFY   | `backend/requirements.txt`            | Add `sqlalchemy`                                  |
| MODIFY   | `frontend/src/App.tsx`                | Add `/history` route                              |
| MODIFY   | `frontend/src/services/api.ts`        | Add `getSessions`, `deleteSession` API calls      |
| MODIFY   | `frontend/src/types/api.ts`           | Add session history types                         |
| MODIFY   | `frontend/src/pages/UploadPage.tsx`   | Add "View History" link                           |
| MODIFY   | `frontend/src/pages/FeedbackPage.tsx` | Support DB-loaded sessions + history link         |

---

## Build Phases

### Phase 1 — Database Setup
- [ ] Install `sqlalchemy`
- [ ] Create `backend/database.py` (engine, session factory, `init_db`)
- [ ] Create `backend/models/session_model.py` (InterviewSession model)
- [ ] Register `init_db()` in `main.py` startup
- [ ] Verify: DB file is created on server start, table exists

### Phase 2 — Backend API
- [ ] Add `SessionSummary`, `SessionDetail` schemas to `schemas.py`
- [ ] Modify `_run_pipeline()` in `analyze.py` to persist session to DB
- [ ] Create `routers/sessions.py` with list / get / delete endpoints
- [ ] Register sessions router in `main.py`
- [ ] Test endpoints with curl

### Phase 3 — Frontend History Page
- [ ] Add session history types to `types/api.ts`
- [ ] Add API functions to `services/api.ts`
- [ ] Build `HistoryPage.tsx` with search, sort, session cards, delete
- [ ] Add `/history` route to `App.tsx`
- [ ] Add "View History" links to UploadPage and FeedbackPage

### Phase 4 — Integration & Polish
- [ ] Modify FeedbackPage to load from DB when in-memory session is gone
- [ ] Empty state for no sessions
- [ ] Delete confirmation modal
- [ ] Responsive layout
- [ ] Loading skeletons on history page

---

## Verification Plan

### Automated Tests
- Run backend with `uvicorn main:app --reload`
- `curl POST /api/analyze` → complete a session → verify it appears in `GET /api/sessions`
- `curl GET /api/sessions/{id}` → verify full feedback is returned
- `curl DELETE /api/sessions/{id}` → verify session is removed
- Restart server → verify sessions persist (SQLite file survives restart)

### Browser Tests
- Upload a session → wait for feedback → navigate to `/history` → verify session card appears
- Click a session card → verify full feedback renders
- Delete a session → verify it's removed from the list
- Search by question text → verify filtering works

### Manual Verification
- Kill and restart the backend → confirm sessions are still in history
- Verify the SQLite file exists at `backend/interview_coach.db`
