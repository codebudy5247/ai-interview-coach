# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Interview Coach is an AI-powered mock interview practice tool. Users upload an MP3 of their interview answer, and the app transcribes it using Whisper, then analyzes it using Azure OpenAI (primary) with automatic Gemini API fallback. Audio files are stored via ImageKit for cloud storage.

## Running the Project

### Prerequisites (one-time setup)
```bash
# Install FFmpeg (required by Whisper)
brew install ffmpeg
```

Feedback runs on cloud providers (Azure OpenAI primary, Gemini fallback) — no local LLM to install. Configure keys in `backend/.env` (see `.env.example`).

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API runs at http://localhost:8000, docs at http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
UI runs at http://localhost:5173

## Architecture

### Backend (FastAPI)
- **main.py**: App entry point, CORS config, router registration
- **routers/analyze.py**: Core API endpoints (`/api/analyze`, `/api/progress`, `/api/feedback`, `/api/cleanup`)
- **routers/sessions.py**: Session history management
- **services/whisper_service.py**: Audio transcription using OpenAI Whisper
- **services/feedback_service.py**: AI feedback generation with Azure OpenAI → Gemini fallback + retry logic
- **services/imagekit_service.py**: ImageKit integration for audio file storage
- **utils/file_handler.py**: File upload/save, report generation, temp file cleanup
- **models/schemas.py**: Pydantic request/response models

### Frontend (React + Vite + TailwindCSS)
- **src/App.tsx**: Main router configuration
- **src/pages/**: UploadPage, ProgressPage, FeedbackPage
- **src/components/**: AudioUploader and UI components
- **src/services/api.ts**: Axios API client
- **src/types/api.ts**: TypeScript type definitions

### Pipeline Flow
1. User submits question + audio file via `POST /api/analyze`
2. Backend returns `session_id` immediately
3. Background thread runs pipeline: upload to ImageKit → transcribe → generate feedback → save report
4. Client polls via SSE (`GET /api/progress/{session_id}`) for real-time status updates
5. Client fetches final feedback via `GET /api/feedback/{session_id}`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/analyze` | Upload audio + question, returns session_id |
| GET | `/api/progress/{session_id}` | SSE stream of pipeline steps |
| GET | `/api/feedback/{session_id}` | Get structured feedback JSON |
| GET | `/api/report/{session_id}` | Download .txt feedback report |
| DELETE | `/api/cleanup/{session_id}` | Remove session data |
| GET | `/api/sessions` | List session history |
| GET | `/api/sessions/{session_id}` | Get session details |

## Key Configuration

API keys are stored in `backend/.env`:
- `AZURE_OPENAI_API_KEY`: Primary AI provider key. Blank → skip Azure, use Gemini directly
- `AZURE_OPENAI_ENDPOINT`: e.g. `https://<resource>.openai.azure.com`
- `AZURE_OPENAI_DEPLOYMENT`: chat model deployment name
- `AZURE_OPENAI_API_VERSION`: Defaults to `2024-10-21`
- `GEMINI_API_KEY`: Fallback AI provider (get from https://aistudio.google.com/app/apikey)
- `MAX_RETRIES`: Per-provider retry count before fallback
- `IMAGEKIT_PUBLIC_KEY`: ImageKit public key (get from https://imagekit.io/dashboard/developer)
- `IMAGEKIT_PRIVATE_KEY`: ImageKit private key
- `IMAGEKIT_URL_ENDPOINT`: ImageKit URL endpoint