# Implementation Plan: Code Snippet Input Support

## Overview

Extend the Interview Coach to accept an **optional code snippet** alongside the question and audio file. When provided, the AI evaluates the candidate's explanation/discussion of the code, producing more contextual feedback.

## Context

Currently, the pipeline is: **question + audio → transcribe → feedback**. Many interview questions reference code (e.g., "Explain what this function does", "Find the bug in this snippet", "What's the time complexity?"). Without the code in the prompt, the AI judges the answer blindly and can't verify correctness against the actual code.

---

## Input Design Recommendation

### Approach: Progressive Disclosure with "Attach Code" Toggle

Rather than a standalone textarea always visible, use a **toggle button** that reveals a code editor area. This is better than the alternatives because:

```
┌─────────────────────────────────────────────┐
│  Interview Question                         │
│  ┌─────────────────────────────────────────┐ │
│  │ "Explain what this function does..."    │ │
│  └─────────────────────────────────────────┘ │
│                                             │
│  [🔗 Attach Code Snippet]  ← toggle button │
│                                             │
│  ┌─ When expanded ────────────────────────┐ │
│  │ [Python ▼]              [5000 / 5000]  │ │
│  │ ┌─────────────────────────────────────┐ │ │
│  │ │ def fibonacci(n):                   │ │ │
│  │ │     if n <= 1:                      │ │ │
│  │ │         return n                    │ │ │
│  │ │     return fib(n-1) + fib(n-2)      │ │ │
│  │ └─────────────────────────────────────┘ │ │
│  │                      [✕ Remove Code]   │ │
│  └────────────────────────────────────────┘ │
│                                             │
│  🎙 Audio Upload / Record                  │
│  ┌─────────────────────────────────────────┐ │
│  │  ...existing AudioUploader...           │ │
│  └─────────────────────────────────────────┘ │
│                                             │
│  [🚀 Analyze My Answer]                    │
└─────────────────────────────────────────────┘
```

### Why this approach?

| Approach | Verdict | Reason |
|----------|---------|--------|
| **Toggle button (recommended)** | ✅ | Clean default UX, code area only appears when needed, language selector aids prompt quality |
| Always-visible textarea | ❌ | Clutters the form for the common case (no code), makes the form intimidating |
| Rich text / markdown in question field | ❌ | Mixes concerns, no syntax highlighting, easy to mess up formatting |
| Tabbed interface ("Question only" vs "Question + Code") | ❌ | Over-engineered, hides the question input behind tab navigation |
| File upload for code | ❌ | Friction for short snippets (most interview code is <50 lines), need to parse file types |

### Key Design Details

- **Language selector dropdown** — optional, defaults to "Auto-detect". Lets the AI know the language for better analysis. Include common interview languages: Python, JavaScript, TypeScript, Java, C++, Go, Rust, SQL, Other.
- **Monospace textarea** — `font-family: monospace`, preserves whitespace, tab key inserts spaces (not focus change).
- **Character limit** — 5,000 chars with a visible counter (most interview snippets are <100 lines).
- **"Remove Code" button** — clears the snippet and collapses the section back.
- **Smooth expand/collapse animation** — matches the app's existing dark theme aesthetic.

---

## Implementation Steps

### Phase 1: Backend Changes

#### 1.1 [MODIFY] [analyze.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/routers/analyze.py)

Add `code_snippet` and `code_language` as optional `Form` parameters to the `POST /api/analyze` endpoint:

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    background_tasks: BackgroundTasks,
    question: str = Form(...),
    audio: UploadFile = File(...),
    code_snippet: str = Form(None),       # NEW — optional
    code_language: str = Form(None),      # NEW — optional (e.g., "python")
):
```

Store in session dict:
```python
_sessions[session_id] = {
    "question": question,
    "audio_path": str(audio_path),
    "code_snippet": code_snippet,        # NEW
    "code_language": code_language,       # NEW
    ...
}
```

Pass to `get_feedback()` in `_run_pipeline()`:
```python
feedback = get_feedback(
    question, transcript,
    code_snippet=session.get("code_snippet"),    # NEW
    code_language=session.get("code_language"),   # NEW
    on_status=feedback_status_callback,
)
```

Also persist `code_snippet` and `code_language` in the DB session object.

#### 1.2 [MODIFY] [feedback_service.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/services/feedback_service.py)

**Update `build_prompt()`** to accept optional code context:

```python
def build_prompt(
    question: str,
    transcript: str,
    code_snippet: str | None = None,
    code_language: str | None = None,
) -> str:
```

When `code_snippet` is provided, inject a code context section between the question and the candidate's answer:

```
## Interview Question
{question}

## Code Snippet Under Discussion
The interviewer provided this code for the candidate to discuss:
```{code_language or ''}
{code_snippet}
```

## Candidate's Answer (transcribed from audio)
{transcript}
```

Also update the rubric instructions to tell the AI:
- If code is present, verify the candidate's explanation against the actual code behavior
- Score `correctness` based on whether the candidate accurately described what the code does
- Note any bugs/issues in the code that the candidate missed

**Update `get_feedback()`** signature:

```python
def get_feedback(
    question: str,
    transcript: str,
    code_snippet: str | None = None,
    code_language: str | None = None,
    on_status: callable = None,
) -> dict:
```

#### 1.3 [MODIFY] [schemas.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/models/schemas.py)

Add optional fields to `FeedbackResponse`:

```python
class FeedbackResponse(BaseModel):
    ...existing fields...
    code_snippet: Optional[str] = None
    code_language: Optional[str] = None
```

#### 1.4 [MODIFY] [session_model.py](file:///Users/ujjwal/Desktop/code/interview-coach/backend/models/session_model.py)

Add nullable columns:

```python
class InterviewSession(Base):
    ...existing columns...
    code_snippet = Column(Text, nullable=True)
    code_language = Column(String, nullable=True)
```

Since we use SQLite with `create_all()`, new nullable columns will be added automatically for new databases. For existing databases, we'll need a migration step (reset or manual ALTER TABLE).

---

### Phase 2: Frontend Changes

#### 2.1 [NEW] [CodeSnippetInput.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/components/CodeSnippetInput.tsx)

New component with:

- **Toggle button** ("🔗 Attach Code Snippet") styled as a ghost button matching the existing dark theme
- **Collapsible content area** with smooth height animation
- **Language selector dropdown** — `<select>` with options: Auto-detect, Python, JavaScript, TypeScript, Java, C++, Go, Rust, SQL, Other
- **Monospace `<textarea>`** — dark bg (`bg-slate-800`), `font-mono`, `resize-y`, `rows={8}`
- **Tab key handler** — inserts 2 spaces instead of changing focus
- **Character counter** — "123 / 5000" in bottom-right, amber when near limit
- **"✕ Remove Code" button** — clears text + collapses section

Props interface:
```typescript
interface CodeSnippetInputProps {
  code: string;
  language: string;
  onCodeChange: (code: string) => void;
  onLanguageChange: (language: string) => void;
  disabled?: boolean;
}
```

#### 2.2 [MODIFY] [UploadPage.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/pages/UploadPage.tsx)

Add state for code snippet and language, render `CodeSnippetInput` between `QuestionInput` and `AudioUploader`:

```tsx
const [codeSnippet, setCodeSnippet] = useState('')
const [codeLanguage, setCodeLanguage] = useState('auto')

// In JSX, between QuestionInput and AudioUploader:
<CodeSnippetInput
  code={codeSnippet}
  language={codeLanguage}
  onCodeChange={setCodeSnippet}
  onLanguageChange={setCodeLanguage}
  disabled={loading}
/>
```

Update submit handler to pass code to `analyzeAnswer()`.

#### 2.3 [MODIFY] [api.ts](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/services/api.ts)

Update `analyzeAnswer()` to accept optional code params:

```typescript
export async function analyzeAnswer(
  question: string,
  audioFile: File,
  codeSnippet?: string,
  codeLanguage?: string,
): Promise<AnalyzeResponse> {
  const form = new FormData()
  form.append('question', question)
  form.append('audio', audioFile)
  if (codeSnippet?.trim()) {
    form.append('code_snippet', codeSnippet)
    if (codeLanguage && codeLanguage !== 'auto') {
      form.append('code_language', codeLanguage)
    }
  }
  ...
}
```

#### 2.4 [MODIFY] [api.ts (types)](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/types/api.ts)

Add optional fields to `FeedbackResponse`:

```typescript
export interface FeedbackResponse {
  ...existing fields...
  code_snippet?: string
  code_language?: string
}
```

#### 2.5 [MODIFY] [FeedbackReport.tsx](file:///Users/ujjwal/Desktop/code/interview-coach/frontend/src/components/FeedbackReport.tsx)

Add a new collapsible section "💻 Code Snippet" (only rendered when `feedback.code_snippet` exists):

```tsx
{feedback.code_snippet && (
  <Section id="section-code" emoji="💻" title="Code Snippet">
    {feedback.code_language && (
      <span className="text-xs text-slate-500 mb-2 block">
        Language: {feedback.code_language}
      </span>
    )}
    <pre className="text-sm text-slate-300 bg-slate-800 rounded-lg p-4 overflow-x-auto font-mono">
      <code>{feedback.code_snippet}</code>
    </pre>
  </Section>
)}
```

---

### Phase 3: Database Migration

Since we use SQLite with `Base.metadata.create_all()`, new nullable columns won't be added to existing tables. Two options:

1. **Reset DB** (dev-friendly): Delete `interview_coach.db` and let it recreate on next startup
2. **Manual migration**: Run `ALTER TABLE sessions ADD COLUMN code_snippet TEXT; ALTER TABLE sessions ADD COLUMN code_language VARCHAR;`

Recommend option 1 for development since this is a local dev project.

---

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/routers/analyze.py` | Modify | Add `code_snippet` + `code_language` form params, store in session, pass to pipeline |
| `backend/services/feedback_service.py` | Modify | Accept code params in `build_prompt()` and `get_feedback()`, inject code context into prompt |
| `backend/models/schemas.py` | Modify | Add optional `code_snippet`, `code_language` to `FeedbackResponse` |
| `backend/models/session_model.py` | Modify | Add nullable `code_snippet`, `code_language` columns |
| `frontend/src/components/CodeSnippetInput.tsx` | **Create** | New toggle + textarea + language selector component |
| `frontend/src/pages/UploadPage.tsx` | Modify | Wire up `CodeSnippetInput`, pass code to API |
| `frontend/src/services/api.ts` | Modify | Send `code_snippet` + `code_language` in FormData |
| `frontend/src/types/api.ts` | Modify | Add optional code fields to TypeScript types |
| `frontend/src/components/FeedbackReport.tsx` | Modify | Show code snippet section on feedback page |

## API Contract

### Request

```
POST /api/analyze
Content-Type: multipart/form-data

question:      string  (required)
audio:         file    (required)
code_snippet:  string  (optional)
code_language: string  (optional, e.g., "python", "javascript")
```

### Response (unchanged)

```json
{ "session_id": "uuid-string" }
```

---

## Verification Plan

### Test Cases

1. **With code**: Submit question + audio + code snippet (Python) → verify code appears in prompt → AI feedback references the code
2. **Without code**: Submit question + audio only → exact same behavior as before, no regressions
3. **Empty code**: Submit question + audio + whitespace-only code → treated as "no code", same as test 2
4. **Long code**: Submit 5000-char code snippet → verify it's stored correctly, no truncation
5. **Language tag**: Submit with `code_language=python` → verify language appears in prompt and feedback page

### UI Verification

1. Toggle button expands/collapses smoothly
2. Language dropdown persists selection
3. Tab key inserts spaces (not focus change)
4. Character counter updates in real-time
5. "Remove Code" clears and collapses
6. Code snippet section shows on feedback page with monospace formatting
7. Component is properly disabled during upload

### Manual Steps

```bash
# 1. Reset DB (optional, for existing data)
rm backend/interview_coach.db

# 2. Start backend
cd backend && uvicorn main:app --reload --port 8000

# 3. Start frontend
cd frontend && npm run dev

# 4. Test at http://localhost:5173
#    - Submit with code → check feedback references code
#    - Submit without code → verify no regression
```