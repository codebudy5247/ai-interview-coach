# 🎯 Interview Coach

> **Practice mock interviews. Get AI-powered feedback. Improve fast.**
>
> Upload an MP3 of your answer → AI transcribes + analyzes → get a detailed feedback report.
> Uses **Gemini API** for feedback (fast, cloud) with automatic **Ollama llama3.2 fallback** (local, offline-safe).

---

## ✨ What It Does

1. You paste the **exact interview question** you were asked
2. You upload your **MP3 answer** (recorded explanation)
3. The app **transcribes** your audio using OpenAI Whisper (runs locally)
4. It sends the **transcript + question** to **Gemini API** for structured feedback
5. If Gemini fails or is unavailable → automatically **retries**, then **falls back to Ollama llama3.2** (local)
6. You get **structured feedback** (scores, strengths, gaps, ideal answer)
7. Feedback is shown in the UI **and** saved as a downloadable `.txt` report

---

## 🗂️ Project Structure

```
interview-coach/
├── backend/                    # Python + FastAPI
│   ├── main.py                 # App entry point, CORS, router registration
│   ├── requirements.txt        # Python dependencies
│   ├── routers/
│   │   └── analyze.py          # API route handlers
│   ├── services/
│   │   ├── whisper_service.py  # MP3 → transcript  (Phase 2)
│   │   └── feedback_service.py # transcript → feedback via Gemini (primary) / Ollama (fallback) + retry  (Phase 2)
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   ├── utils/
│   │   └── file_handler.py     # File save/delete + report formatting
│   ├── temp/                   # Auto-created: temp MP3 uploads
│   └── reports/                # Auto-created: saved .txt feedback reports
│
├── frontend/                   # React + Vite + TailwindCSS  (Phase 5)
│
├── interview-coach-implementation-plan.md
└── README.md
```

---

## ⚙️ Prerequisites

Install these system dependencies **once** before anything else.

### 1. FFmpeg (required by Whisper)
```bash
brew install ffmpeg
```

### 2. Ollama + llama3.2 model *(fallback — optional but recommended)*
```bash
# Install Ollama
brew install ollama

# Start the Ollama server (keep this running in a terminal)
ollama serve

# Pull the model (one-time, ~2 GB download)
ollama pull llama3.2
```

> **Note:** Ollama is the **fallback** provider. If you have a Gemini API key, Ollama is only used when Gemini fails. Keep `ollama serve` running so the fallback is always ready.

### 3. Gemini API Key *(primary AI provider)*
```bash
# 1. Get a free key at: https://aistudio.google.com/app/apikey
# 2. Copy the example env file
cp backend/.env.example backend/.env
# 3. Paste your key into backend/.env
#    GEMINI_API_KEY=your_key_here
```

> If `GEMINI_API_KEY` is missing or blank, the app will **skip Gemini** and use Ollama directly.

---

## 🔧 Backend Setup

```bash
# 1. Navigate to the backend folder
cd backend

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Start the backend server
uvicorn main:app --reload --port 8000
```

The API will be running at **http://localhost:8000**

> `--reload` enables hot-reloading on file changes (development only).

---

## 🖥️ Frontend Setup *(Phase 5 — coming soon)*

```bash
cd frontend
npm install
npm run dev
```

The UI will be running at **http://localhost:5173**

---

## 🚀 Quick Start (after first-time setup)

Open **3 terminal tabs**:

| Tab | Command | Purpose |
|-----|---------|---------|
| 1 | `ollama serve` | Run the Ollama fallback LLM |
| 2 | `cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000` | Run the API |
| 3 | `cd frontend && npm run dev` | Run the UI *(Phase 5)* |

> Tab 1 (Ollama) is only strictly needed if Gemini is unavailable, but it's good practice to keep it running.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze` | Upload MP3 + question → returns `session_id` |
| `GET` | `/api/progress/{session_id}` | SSE stream of pipeline steps |
| `GET` | `/api/feedback/{session_id}` | Get structured feedback JSON |
| `GET` | `/api/report/{session_id}` | Download `.txt` feedback report |
| `DELETE` | `/api/cleanup/{session_id}` | Remove session data + temp files |

### Test the upload endpoint with curl
```bash
curl -X POST http://localhost:8000/api/analyze \
  -F "question=Explain how closures work in JavaScript" \
  -F "audio=@/path/to/your/answer.mp3"

# Returns:
# {"session_id": "d37b59ef-cac7-4bba-a71c-f0c3ea1bb3e2"}
```

Interactive API docs available at **http://localhost:8000/docs**

---

## 🏗️ Build Phases

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Backend foundation — FastAPI, file upload, folder structure | ✅ Done |
| **Phase 2** | AI pipeline — Whisper + Gemini feedback (Ollama fallback + retry) | 🔜 Next |
| **Phase 3** | SSE progress streaming (incl. retrying events) | 🔜 |
| **Phase 4** | Report saving + file download | 🔜 |
| **Phase 5** | React + Vite frontend | 🔜 |
| **Phase 6** | Polish, error handling (both providers), mobile layout | 🔜 |

---

## 🧠 AI Models Used

| Task | Model | Provider | Notes |
|------|-------|----------|-------|
| Audio transcription | `openai/whisper-base` | Local Python library | Always local |
| Answer feedback | `gemini-1.5-flash` | Google Gemini API | Primary — needs `GEMINI_API_KEY` |
| Answer feedback (fallback) | `llama3.2` | Ollama (local) | Triggered when Gemini fails/unavailable |

**Retry mechanism:** Gemini is retried up to `MAX_RETRIES` times before falling back to Ollama. Ollama is also retried before raising a final error. Both values are configurable in `backend/.env`.

---

## 📄 Feedback Report Format

The `.txt` report saved to `backend/reports/` looks like this:

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
  Correctness   : 8/10 — Explained lexical scope correctly
  Clarity       : 7/10 — Good pacing but some parts were unclear
  Structure     : 6/10 — Jumped between ideas without clear flow
  Relevance     : 8/10 — Stayed on topic throughout

✅ WHAT YOU DID WELL ...
📌 WHAT YOU MISSED ...
💡 HOW TO IMPROVE ...
📝 YOUR TRANSCRIPT ...
🏆 IDEAL ANSWER ...
```

---

## 🔮 V2 Roadmap

- 🎥 Video / screen recording upload (MP4)
- 📚 Session history and past feedback review
- 🔐 User accounts and personal dashboard
- 📊 Score trends over time
- 🎙️ In-browser audio recording (no upload needed)
- 🔤 Filler word detection (um, uh, like...)
- ⏱️ Speaking pace analysis (words per minute)
