# Implementation Plan: Code Snippet Input Support

## Overview

Extend the Interview Coach app to accept an optional code snippet as input alongside the question and audio file. The AI will consider the code snippet when providing feedback.

## Context

Currently, users upload an MP3/WebM audio file along with a text question. The app transcribes the audio and provides feedback on the answer. Users want to optionally include a code snippet that the AI should analyze or reference (e.g., "Explain what this code does" or "Find bugs in this snippet").

## Input Design

**Recommended: Collapsible optional field**

A separate, collapsible "Add code snippet (optional)" section that expands when clicked. This approach is preferred because:
- Not all questions require code snippets
- Code needs special handling (monospace formatting, preserving whitespace)
- Keeps the UI clean when code isn't needed
- Clear UX: clear label indicates optional nature

### Why not other approaches?

| Approach | Reason for rejection |
|----------|---------------------|
| Rich text in question field | Would require parsing/markdown support, harder to validate |
| Single combined input | Loses optional nature - code becomes visually required |
| Tabbed interface ("Question only" vs "Question + Code") | More complex, less intuitive for common case (no code) |

## Implementation Steps

### Step 1: Backend API (`backend/routers/analyze.py`)

- Add optional `code_snippet: str = Form(None)` parameter to `POST /api/analyze`
- Store code_snippet in session dictionary
- Pass to feedback service

**Key changes:**
- Line ~179: Add `code_snippet: str = Form(None)` parameter
- Line ~195: Add `"code_snippet": code_snippet` to session dict
- Line ~116: Pass `code_snippet` to `get_feedback()`

### Step 2: Backend Schema (`backend/models/schemas.py`)

- Add `code_snippet: Optional[str] = None` to `FeedbackResponse`
- Update `InterviewSession` model (in `session_model.py`) to store code_snippet

### Step 3: Feedback Service (`backend/services/feedback_service.py`)

- Modify `build_prompt()` function to include code context
- When code snippet provided, add context section:
  ```
  The candidate provided this code snippet for reference:
  
  ```python
  <code_snippet>
  ```
  ```
- Include this before the question in the prompt

### Step 4: Frontend Component (`frontend/src/components/CodeSnippetInput.tsx`)

Create new component with:
- Collapsible header with toggle button
- Textarea with monospace font (font-mono)
- Character limit indicator (e.g., 5000 chars)
- Syntax highlighting optional (stretch goal)

### Step 5: Frontend Integration (`frontend/src/pages/UploadPage.tsx`)

- Import and add `CodeSnippetInput` component after `QuestionInput`
- Pass codeSnippet to API service

### Step 6: Frontend API (`frontend/src/services/api.ts`)

- Update `analyzeAnswer()` to include `codeSnippet` in FormData (if provided and non-empty)

### Step 7: Frontend Types (`frontend/src/types/api.ts`)

- Add `codeSnippet?: string` to relevant types if needed

## Files to Modify

| File | Change Type |
|------|-------------|
| `backend/routers/analyze.py` | Modify |
| `backend/models/schemas.py` | Modify |
| `backend/models/session_model.py` | Modify |
| `backend/services/feedback_service.py` | Modify |
| `frontend/src/components/CodeSnippetInput.tsx` | Create |
| `frontend/src/pages/UploadPage.tsx` | Modify |
| `frontend/src/services/api.ts` | Modify |
| `frontend/src/types/api.ts` | Modify |

## API Contract

### Request

```
POST /api/analyze
Content-Type: multipart/form-data

question: string (required)
audio: file (required)
code_snippet: string (optional)
```

### Response

```json
{
  "session_id": "uuid-string"
}
```

## Database Schema

Add to `InterviewSession` table:
- `code_snippet` (TEXT, nullable)

## Verification

### Test Cases

1. **Full input test**: Submit question + audio + code_snippet
   - Verify code_snippet is stored in session
   - Verify feedback includes analysis of code
   - Verify code appears in feedback response

2. **Backward compatibility**: Submit question + audio only (no code)
   - Should work exactly as before
   - No regressions in existing functionality

3. **Empty code test**: Submit question + audio + empty code_snippet
   - Should be treated as no code provided
   - Same behavior as test case 2

4. **UI test**: Verify collapsible component
   - Expands/collapses on click
   - Code preserves formatting/whitespace
   - Character limit is enforced

### Manual Verification Steps

1. Start backend: `cd backend && uvicorn main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173
4. Submit interview with code snippet
5. Verify feedback shows code analysis
6. Submit interview without code snippet
7. Verify no regressions