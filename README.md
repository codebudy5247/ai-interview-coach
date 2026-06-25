# 🎯 Interview Coach

> **Practice mock interviews. Get AI-powered feedback. Improve fast.**
>
> Upload an MP3 of your answer → AI transcribes + analyzes → get a detailed feedback report.
> Uses **Azure OpenAI** for feedback (primary) with automatic **Gemini API fallback**.

---

## ✨ What It Does

1. You paste the **exact interview question** you were asked
2. You **record your answer** directly in the browser OR upload an audio file (MP3, WAV, M4A, OGG)
3. The app **transcribes** your audio using OpenAI Whisper (runs locally)
4. It sends the **transcript + question** to **Azure OpenAI** for structured feedback
5. If Azure fails or is unavailable → automatically **retries**, then **falls back to Gemini API**
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
│   │   ├── whisper_service.py  # MP3 → transcript
│   │   └── feedback_service.py # transcript → feedback via Azure OpenAI (primary) / Gemini (fallback) + retry
│   ├── models/
│   │   └── schemas.py          # Pydantic request/response models
│   ├── utils/
│   │   └── file_handler.py     # File save/delete + report formatting
│   ├── temp/                   # Auto-created: temp MP3 uploads
│   └── reports/                # Auto-created: saved .txt feedback reports
│
├── frontend/                   # React + Vite + TailwindCSS
│
├── plan
└── README.md
```

---

## ⚙️ Prerequisites

Install these system dependencies **once** before anything else.

### 1. FFmpeg (required by Whisper)
```bash
brew install ffmpeg
```

### 2. Azure OpenAI *(primary AI provider)*
```bash
# 1. Copy the example env file
cp backend/.env.example backend/.env
# 2. Fill in your Azure OpenAI values in backend/.env:
#    AZURE_OPENAI_API_KEY=your_key_here
#    AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com
#    AZURE_OPENAI_DEPLOYMENT=your_chat_deployment_name
#    AZURE_OPENAI_API_VERSION=2024-10-21
```

> If `AZURE_OPENAI_API_KEY` is missing or blank, the app will **skip Azure** and use Gemini directly.

### 3. Gemini API Key *(fallback provider)*
```bash
# Get a free key at: https://aistudio.google.com/app/apikey
# Add it to backend/.env:
#    GEMINI_API_KEY=your_key_here
```

> Gemini is the **fallback** — used only when Azure fails or is unavailable. At least one provider must be configured.

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

## 🖥️ Frontend Setup

```bash
cd frontend
pnpm install
pnpm run dev
```

The UI will be running at **http://localhost:5173**

---

## 🚀 Quick Start (after first-time setup)

Open **2 terminal tabs**:

| Tab | Command | Purpose |
|-----|---------|---------|
| 1 | `cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8000` | Run the API |
| 2 | `cd frontend && pnpm dev` | Run the UI |

> Feedback runs on Azure OpenAI (cloud), with Gemini as an automatic fallback — no local LLM process required.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze` | Upload audio + question → returns `session_id` |
| `GET` | `/api/progress/{session_id}` | SSE stream of pipeline steps |
| `GET` | `/api/feedback/{session_id}` | Get structured feedback JSON |
| `GET` | `/api/report/{session_id}` | Download `.txt` feedback report |
| `DELETE` | `/api/cleanup/{session_id}` | Remove session data + temp files |
| `GET` | `/api/sessions` | List session history (with search/sort) |
| `GET` | `/api/sessions/{session_id}` | Get full session details |
| `DELETE` | `/api/sessions/{session_id}` | Delete a session from history |

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

## 🧠 AI Models Used

| Task | Model | Provider | Notes |
|------|-------|----------|-------|
| Audio transcription | `openai/whisper-base` | Local Python library | Always local — supports MP3, WAV, M4A, OGG |
| Answer feedback | Azure deployment (e.g. `gpt-4o`) | Azure OpenAI | Primary — needs `AZURE_OPENAI_*` vars |
| Answer feedback (fallback) | `gemini-3-flash-preview` | Google Gemini API | Triggered when Azure fails/unavailable |

**Retry mechanism:** Azure is retried up to `MAX_RETRIES` times before falling back to Gemini. Gemini is also retried before raising a final error. Both values are configurable in `backend/.env`.

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

- 🔐 User accounts and personal dashboard
- 📊 Score trends over time
- 🔤 Filler word detection (um, uh, like...)
- ⏱️ Speaking pace analysis (words per minute)

