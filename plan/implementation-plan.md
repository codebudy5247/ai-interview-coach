# 🎯 Interview Coach — Full Implementation Plan (V1)

> **Stack:** Python + FastAPI + React + Vite + TailwindCSS + Whisper + Gemini API (primary) + Ollama llama3.2 (fallback)
> **Platform:** MacBook Air M1 8GB
> **V1 Scope:** User submits an interview question (text) + their answer (MP3) → AI transcribes + analyzes → returns structured feedback + saves as .txt report

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Backend Plan](#4-backend-plan)
5. [Frontend Plan](#5-frontend-plan)
6. [AI Pipeline Plan](#6-ai-pipeline-plan)
7. [API Endpoints](#7-api-endpoints)
8. [Data Models & Schemas](#8-data-models--schemas)
9. [Feedback Report Format](#9-feedback-report-format)
10. [UI Screens Plan](#10-ui-screens-plan)
11. [Build Phases](#11-build-phases)
12. [Prerequisites & Installation](#12-prerequisites--installation)
13. [V2 Roadmap](#13-v2-roadmap)

---

## 1. Project Overview

### What it does
- User pastes the **exact interview question** they were asked
- User uploads their **MP3 answer** (recorded explanation)
- App **transcribes** the audio using Whisper (runs locally)
- App sends **transcript + question** to **Gemini API** (primary) for feedback
- If Gemini fails/is unavailable, **falls back to llama3.2 via Ollama** (local) with a retry mechanism
- AI returns **structured feedback** on their answer
- Feedback is shown in the UI **and** saved as a `.txt` file for download

### What it does NOT do in V1
- No video/screen recording processing (V2)
- No user accounts or login (V2)
- No history of past sessions (V2)
- No in-browser audio recording — upload MP3 only (V2)

---

## 2. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite | UI framework |
| Styling | TailwindCSS | UI styling |
| HTTP Client | Axios | API calls from frontend |
| Backend | Python + FastAPI | REST API server |
| Transcription | OpenAI Whisper (local) | MP3 → text |
| AI Feedback (primary) | Google Gemini API | Analyze answer, generate feedback (cloud) |
| AI Feedback (fallback) | Ollama + llama3.2 (local) | Fallback if Gemini fails/unavailable |
| Retry Logic | Custom Python retry wrapper | Retries each provider before falling back |
| Progress Updates | SSE (Server Sent Events) | Live pipeline progress to frontend |
| File Handling | Python `shutil` + `tempfile` | Temp MP3 storage |
| Report Saving | Python file I/O | Save feedback as .txt |

---

## 3. Project Structure

```
interview-coach/
│
├── backend/
│   ├── main.py                      # FastAPI app, CORS config, router registration
│   ├── requirements.txt             # All Python dependencies
│   │
│   ├── routers/
│   │   └── analyze.py               # All API route handlers
│   │
│   ├── services/
│   │   ├── whisper_service.py       # MP3 → transcript using Whisper
│   │   └── feedback_service.py      # transcript + question → feedback JSON via Gemini (primary) / Ollama (fallback) + retry
│   │
│   ├── models/
│   │   └── schemas.py               # Pydantic request/response models
│   │
│   ├── utils/
│   │   └── file_handler.py          # Save/delete temp files, format + save .txt report
│   │
│   ├── temp/                        # Temp folder for uploaded MP3 files (auto cleaned)
│   └── reports/                     # Saved .txt feedback reports
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx                  # Main app, routing
│   │   │
│   │   ├── pages/
│   │   │   ├── UploadPage.jsx       # Question input + MP3 upload form
│   │   │   ├── ProgressPage.jsx     # Live SSE progress steps
│   │   │   └── FeedbackPage.jsx     # Final feedback report display
│   │   │
│   │   ├── components/
│   │   │   ├── AudioUploader.jsx    # Drag & drop / click to upload MP3
│   │   │   ├── QuestionInput.jsx    # Textarea for interview question
│   │   │   ├── ProgressTracker.jsx  # Step-by-step progress UI (SSE driven)
│   │   │   └── FeedbackReport.jsx   # Renders full feedback JSON into UI
│   │   │
│   │   └── services/
│   │       └── api.js               # All axios calls to FastAPI backend
│   │
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

---

## 4. Backend Plan

### `main.py`
- Initialize FastAPI app
- Configure CORS (allow React dev server at `localhost:5173`)
- Register routers from `routers/analyze.py`
- Create `temp/` and `reports/` folders on startup if they don't exist

### `routers/analyze.py`
Handles all route logic:
- Accept MP3 upload + question text
- Generate unique `session_id` (UUID)
- Save MP3 to `temp/{session_id}.mp3`
- Trigger background pipeline task
- Return `session_id` to frontend
- Serve SSE progress stream
- Return final feedback JSON
- Serve `.txt` report file for download
- Handle cleanup of temp files

### `services/whisper_service.py`
```
Input  : path to MP3 file
Process: load whisper model ("base") → transcribe
Output : transcript string

Model choice for M1 8GB:
  "tiny"  → fastest (~30s), less accurate
  "base"  → recommended balance (~1 min) ✅
  "small" → more accurate (~2 min), slower
```

### `services/feedback_service.py`
```
Input  : question (str) + transcript (str)
Process: build prompt → try Gemini → on failure retry → fallback to Ollama → parse JSON
Output : feedback dict (structured)

Provider chain:
  PRIMARY  → Google Gemini API (gemini-1.5-flash)
               Uses: google-genai Python SDK
               Requires: GEMINI_API_KEY in .env
               Retries: up to MAX_RETRIES (default: 2) with RETRY_DELAY seconds between

  FALLBACK → Ollama local model (llama3.2)
               Uses: ollama.chat(model="llama3.2", messages=[...])
               Triggered when: Gemini exhausts all retries (API error, timeout, quota)
               Retries: up to MAX_RETRIES on Ollama too before raising final error

Retry mechanism:
  - Each provider is attempted up to MAX_RETRIES times
  - Exponential-friendly fixed delay (RETRY_DELAY seconds) between attempts
  - If both providers fail all retries → raises FeedbackServiceError
  - SSE sends an event on each retry so the frontend can show "Retrying..."
```

### `utils/file_handler.py`
```
Functions:
  save_upload(file, session_id)     → saves MP3 to temp/
  delete_temp(session_id)           → removes MP3 after processing
  format_feedback_txt(feedback, question, transcript, session_id) → formatted string
  save_report_txt(formatted_str, session_id) → saves to reports/{session_id}_feedback.txt
```

### `models/schemas.py`
```
AnalyzeResponse     → session_id: str
FeedbackScore       → score: int, feedback: str
FeedbackResponse    → overall_score, scores, what_went_well,
                       what_was_missed, improvements,
                       ideal_answer, transcript
```

---

## 5. Frontend Plan

### `App.jsx`
- React Router with 3 routes:
  - `/` → UploadPage
  - `/progress/:sessionId` → ProgressPage
  - `/feedback/:sessionId` → FeedbackPage

### `pages/UploadPage.jsx`
- Renders `QuestionInput` + `AudioUploader` components
- Validates: question not empty + MP3 file selected
- On submit → calls `api.js → POST /api/analyze`
- On success → navigates to `/progress/:sessionId`

### `pages/ProgressPage.jsx`
- On mount → opens SSE connection to `/api/progress/:sessionId`
- Passes SSE events to `ProgressTracker` component
- On `DONE` event → navigates to `/feedback/:sessionId`
- On `ERROR` event → shows error message

### `pages/FeedbackPage.jsx`
- On mount → calls `GET /api/feedback/:sessionId`
- Passes feedback JSON to `FeedbackReport` component
- Has "Download Report" button → calls `GET /api/report/:sessionId`

### `components/AudioUploader.jsx`
- Drag & drop zone for MP3 files
- Click to open file picker
- Shows selected file name + size
- Validates file type (MP3 only) and size (max 100MB)

### `components/QuestionInput.jsx`
- Textarea for interview question
- Character counter
- Placeholder: `e.g. "Explain how closures work and give a real world example"`
- Tip text: "Paste the exact question asked in your interview for best results"

### `components/ProgressTracker.jsx`
- Receives SSE steps as props
- Renders list of steps with status icons:
  - `○` pending → `⏳` in progress → `🔄` retrying → `✅` done → `❌` failed
- Steps:
  1. Audio uploaded
  2. Transcribing speech...
  3. AI analyzing your answer... *(shows provider: Gemini / Ollama fallback)*
  4. Saving feedback report...
  5. Done!
- On `retrying` status → shows "Retrying with [provider]..." inline beneath the step

### `components/FeedbackReport.jsx`
- Overall score with progress bar
- 4 score cards: Correctness / Clarity / Structure / Relevance
- Expandable sections:
  - ✅ What you did well
  - 📌 What you missed
  - 💡 How to improve
  - 📝 Your transcript (collapsible)
  - 🏆 Ideal answer (collapsible)
- Download button at bottom

### `services/api.js`
```javascript
analyzeAnswer(question, audioFile) → POST /api/analyze (multipart form)
getFeedback(sessionId)             → GET  /api/feedback/:sessionId
getProgressStream(sessionId)       → GET  /api/progress/:sessionId (SSE)
downloadReport(sessionId)          → GET  /api/report/:sessionId
```

---

## 6. AI Pipeline Plan

### Full Sequential Pipeline

```
[1] Save MP3 to temp/
         ↓  SSE: "Audio saved ✅"
[2] whisper_service.py
    → whisper.load_model("base")
    → whisper.transcribe(mp3_path)
    → returns transcript string
         ↓  SSE: "Transcription done ✅"
[3] feedback_service.py  ← UPDATED
    → build prompt with question + transcript
    → [ATTEMPT] Gemini API (gemini-1.5-flash)
         on success → parse JSON → continue
         on failure → retry up to MAX_RETRIES
         if all retries fail → [FALLBACK]
    → [FALLBACK] Ollama (llama3.2)
         on success → parse JSON → continue
         on failure → retry up to MAX_RETRIES
         if all retries fail → raise FeedbackServiceError
         ↓  SSE: "Feedback generated ✅" (or "Retrying..." on each retry)
[4] file_handler.py
    → format feedback as readable txt
    → save to reports/{session_id}_feedback.txt
         ↓  SSE: "Report saved ✅"
[5] delete temp MP3 file
         ↓  SSE: "DONE"
```

### Feedback Provider Logic (feedback_service.py)

```python
MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds

def get_feedback(question, transcript) -> dict:
    prompt = build_prompt(question, transcript)

    # --- PRIMARY: Gemini ---
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return call_gemini(prompt)
        except Exception as e:
            log(f"Gemini attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    # --- FALLBACK: Ollama llama3.2 ---
    log("Gemini exhausted retries. Falling back to Ollama...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return call_ollama(prompt)
        except Exception as e:
            log(f"Ollama attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    raise FeedbackServiceError("Both Gemini and Ollama failed to generate feedback.")
```

### Shared Feedback Prompt (used by both providers)

```
You are a senior software engineer reviewing a mock interview answer.

Interview Question:
"{question}"

Candidate's Answer (transcribed from audio):
"{transcript}"

Evaluate the answer strictly and return ONLY a valid JSON object.
No explanation, no markdown, no extra text — just raw JSON.

{
  "overall_score": 7,
  "scores": {
    "correctness": { "score": 8, "feedback": "..." },
    "clarity":     { "score": 7, "feedback": "..." },
    "structure":   { "score": 6, "feedback": "..." },
    "relevance":   { "score": 8, "feedback": "..." }
  },
  "what_went_well": ["point 1", "point 2"],
  "what_was_missed": ["point 1", "point 2"],
  "improvements": ["suggestion 1", "suggestion 2"],
  "ideal_answer": "A complete ideal answer to this question..."
}
```

---

## 7. API Endpoints

| Method | Endpoint | Request | Response |
|---|---|---|---|
| `POST` | `/api/analyze` | `multipart/form-data` — `question: str`, `audio: File` | `{ session_id: string }` |
| `GET` | `/api/progress/{session_id}` | — | SSE stream of step events |
| `GET` | `/api/feedback/{session_id}` | — | Feedback JSON |
| `GET` | `/api/report/{session_id}` | — | `.txt` file download |
| `DELETE` | `/api/cleanup/{session_id}` | — | `{ success: true }` |

### SSE Event Format
```
data: {"step": "transcribing",  "status": "in_progress", "message": "Transcribing your audio..."}
data: {"step": "transcribing",  "status": "done",        "message": "Transcription complete ✅"}
data: {"step": "analyzing",     "status": "in_progress", "message": "Analyzing with Gemini..."}
data: {"step": "analyzing",     "status": "retrying",    "message": "Retrying with Gemini (attempt 2)..."}
data: {"step": "analyzing",     "status": "retrying",    "message": "Gemini failed. Falling back to Ollama..."}
data: {"step": "analyzing",     "status": "done",        "message": "Feedback generated ✅"}
data: {"step": "done",          "status": "done",        "message": "DONE"}
data: {"step": "error",         "status": "error",       "message": "Both providers failed. Please try again."}
```

---

## 8. Data Models & Schemas

### Request
```python
# multipart form
question: str        # interview question text
audio: UploadFile    # MP3 file
```

### FeedbackScore
```python
class FeedbackScore(BaseModel):
    score: int           # 1-10
    feedback: str        # explanation
```

### FeedbackResponse
```python
class FeedbackResponse(BaseModel):
    overall_score: int
    scores: dict[str, FeedbackScore]   # correctness, clarity, structure, relevance
    what_went_well: list[str]
    what_was_missed: list[str]
    improvements: list[str]
    ideal_answer: str
    transcript: str                    # original whisper transcript
```

---

## 9. Feedback Report Format (.txt)

```
================================================
        INTERVIEW COACH — FEEDBACK REPORT
================================================

Question:
"Explain how closures work and give a real world example"

Date: 04 May 2026  |  Time: 10:32 AM
Session: a3f9c2d1

------------------------------------------------
OVERALL SCORE: 7/10
------------------------------------------------

SCORES
  Correctness  : 8/10 — Explained lexical scope correctly
  Clarity      : 7/10 — Good pacing but some parts were unclear
  Structure    : 6/10 — Jumped between ideas without clear flow
  Relevance    : 8/10 — Stayed on topic throughout

------------------------------------------------
✅ WHAT YOU DID WELL
  • Explained lexical scope correctly
  • Used a good real world analogy (counter function)
  • Covered basic definition well

📌 WHAT YOU MISSED
  • Memory implications of closures
  • Practical use in event handlers and callbacks
  • Did not mention closure in loops (common interview follow-up)

💡 HOW TO IMPROVE
  • Structure: problem first → solution → code example → real use case
  • Keep answer under 3 minutes
  • Practice giving a concrete code example verbally

------------------------------------------------
YOUR TRANSCRIPT
  "So closures are basically when a function remembers
   the variables from its outer scope even after the
   outer function has finished executing..."

------------------------------------------------
🏆 IDEAL ANSWER
  "A closure is a function that retains access to its
   lexical scope even after the outer function has
   finished executing. A classic example is a counter
   function — the inner function closes over the count
   variable, keeping it alive between calls..."

================================================
              Generated by Interview Coach
================================================
```

---

## 10. UI Screens Plan

### Screen 1 — Upload Page
```
┌──────────────────────────────────────────┐
│  🎯 Interview Coach                       │
│  Practice. Get feedback. Improve.         │
│                                          │
│  What was the interview question?        │
│  ┌────────────────────────────────────┐  │
│  │ "Explain how closures work and     │  │
│  │  give a real world example..."     │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
│  💡 Paste the exact question for best    │
│     results                              │
│                                          │
│  Upload your answer (MP3)                │
│  ┌────────────────────────────────────┐  │
│  │   🎵 Drop MP3 here or click        │  │
│  │      to upload  (max 100MB)        │  │
│  └────────────────────────────────────┘  │
│  ✅ answer_closures.mp3 (4.2 MB)         │
│                                          │
│        [🚀 Analyze My Answer]            │
└──────────────────────────────────────────┘
```

### Screen 2 — Progress Page
```
┌──────────────────────────────────────────┐
│  ⏳ Analyzing your answer...              │
│                                          │
│  ✅  Audio uploaded                       │
│  ✅  Transcribing speech...               │
│  ⏳  AI analyzing your answer... [Gemini] │
│  ○   Saving feedback report              │
│  ○   Done                                │
│                                          │
│  Usually ~30s with Gemini, ~1–2 min      │
│  if falling back to Ollama.              │
│  Hang tight!                             │
└──────────────────────────────────────────┘
```

### Screen 3 — Feedback Report Page
```
┌──────────────────────────────────────────┐
│  📋 Feedback Report                       │
│  "Explain how closures work..."          │
│                                          │
│  Overall Score     7 / 10               │
│  ███████░░░                              │
│                                          │
│  ┌──────────┬────────┬────────┬────────┐ │
│  │Correctness│Clarity │Structure│Relevance│
│  │  8/10    │  7/10  │  6/10  │  8/10  │ │
│  │ feedback │feedback│feedback│feedback│ │
│  └──────────┴────────┴────────┴────────┘ │
│                                          │
│  ✅ What you did well          [▾]        │
│  • Explained lexical scope correctly     │
│  • Used a good real world analogy        │
│                                          │
│  📌 What you missed            [▾]        │
│  • Memory implications of closures       │
│  • Use in event handlers                 │
│                                          │
│  💡 How to improve             [▾]        │
│  • Problem → solution → code → use case  │
│                                          │
│  📝 Your Transcript            [▾]        │
│  🏆 Ideal Answer               [▾]        │
│                                          │
│  [📄 Download Feedback Report]           │
│  [🔁 Analyze Another Answer]             │
└──────────────────────────────────────────┘
```

---

## 11. Build Phases

### Phase 1 — Backend Foundation
- [ ] Setup FastAPI project + folder structure
- [ ] `main.py` with CORS + router registration
- [ ] `POST /api/analyze` — accept MP3 + question, save to temp/, return session_id
- [ ] `utils/file_handler.py` — save + delete temp files
- [ ] Test upload endpoint with Postman / curl

### Phase 2 — AI Pipeline
- [ ] `whisper_service.py` — transcribe MP3 → text
- [ ] Test Whisper locally with a sample MP3
- [ ] Create `.env` file with `GEMINI_API_KEY`, `MAX_RETRIES`, `RETRY_DELAY`
- [ ] `feedback_service.py` — implement provider chain:
  - [ ] `build_prompt(question, transcript)` — shared prompt for both providers
  - [ ] `call_gemini(prompt)` — call Gemini API (`gemini-1.5-flash`) via `google-generativeai`
  - [ ] `call_ollama(prompt)` — call `llama3.2` via `ollama.chat()`
  - [ ] `get_feedback(question, transcript)` — retry loop: Gemini (×MAX_RETRIES) → Ollama (×MAX_RETRIES) → raise `FeedbackServiceError`
  - [ ] Skip Gemini gracefully if `GEMINI_API_KEY` is missing/blank
- [ ] Test Gemini feedback with a hardcoded transcript
- [ ] Test Ollama fallback by temporarily revoking the API key
- [ ] Connect both services in sequence in `routers/analyze.py`

### Phase 3 — SSE Progress Streaming
- [ ] Background task in FastAPI for the pipeline
- [ ] SSE endpoint `GET /api/progress/:session_id`
- [ ] Fire SSE events at each pipeline step
- [ ] `GET /api/feedback/:session_id` — return stored feedback JSON

### Phase 4 — Report Saving
- [x] `format_feedback_txt()` in `file_handler.py`
- [x] `save_report_txt()` in `file_handler.py`
- [x] `GET /api/report/:session_id` — serve `.txt` file as download
- [x] Auto-cleanup of temp MP3 after pipeline done

### Phase 5 — Frontend
- [ ] React + Vite + TailwindCSS setup
- [ ] React Router — 3 routes configured
- [ ] `UploadPage` — question input + MP3 upload + submit
- [ ] `api.js` — all API calls centralized
- [ ] `ProgressPage` — SSE listener + ProgressTracker component
- [ ] `FeedbackPage` — fetch feedback + render FeedbackReport component
- [ ] Download report button wired up

### Phase 6 — Polish & Error Handling
- [ ] Validate MP3 file type and size on frontend
- [ ] Backend error handling:
  - [ ] Whisper transcription fails (bad audio, unsupported format)
  - [ ] Gemini API error / quota exceeded → confirm fallback triggers correctly
  - [ ] Ollama not running / model not pulled
  - [ ] Both providers exhaust all retries → return `500` with clear error message
  - [ ] Bad / malformed JSON returned by either provider → retry or raise
  - [ ] Missing or invalid `GEMINI_API_KEY` in `.env` → log warning, skip to Ollama
- [ ] SSE error + retry events handled in frontend (show "Retrying..." state)
- [ ] Empty state for no feedback yet
- [ ] Loading skeletons on FeedbackPage
- [ ] Mobile responsive layout

---

## 12. Prerequisites & Installation

### System Dependencies
```bash
# Install FFmpeg (needed by Whisper internally)
brew install ffmpeg

# Install and start Ollama (used as fallback AI provider)
brew install ollama
ollama serve

# Pull the llama3.2 model
ollama pull llama3.2
```

### Gemini API Key
```bash
# 1. Get a free API key from: https://aistudio.google.com/app/apikey
# 2. Create a .env file in the backend/ folder:
cp backend/.env.example backend/.env
# 3. Add your key:
# GEMINI_API_KEY=your_key_here
```

> If `GEMINI_API_KEY` is missing or blank, the service will **skip Gemini entirely**
> and go straight to Ollama as the primary provider.

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
# Installs: fastapi, uvicorn[standard], python-multipart,
#           openai-whisper, ollama, google-generativeai, python-dotenv

# Run backend
uvicorn main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm create vite@latest . -- --template react
npm install
npm install tailwindcss @tailwindcss/vite
npm install axios
npm install react-router-dom

# Run frontend
npm run dev
```

### `requirements.txt`
```
fastapi
uvicorn[standard]
python-multipart
openai-whisper
ollama
google-genai
python-dotenv
```

### `.env.example`
```
# Google Gemini API key (get one free at https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=

# Feedback provider settings
MAX_RETRIES=2
RETRY_DELAY=2
```

---

## 13. V2 Roadmap

| Feature | Description |
|---|---|
| 🎥 Video upload | Upload MP4 screen recording instead of MP3 |
| 👁️ Screen reading | Extract frames → llava reads code from screen |
| 📚 Session history | Save and review past feedback sessions |
| 🔐 User accounts | Login, personal dashboard |
| 📊 Progress tracking | Score trends over time across topics |
| 🎙️ In-browser recording | Record MP3 directly in the app, no upload needed |
| 🔤 Filler word detection | Count "um", "uh", "like" in transcript |
| ⏱️ Speaking pace | Words per minute analysis |

---

> **Start with Phase 1 — Backend Foundation.**
> Get the upload endpoint working first, then layer in AI services one at a time.
