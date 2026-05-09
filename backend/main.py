from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.file_handler import ensure_dirs
from database import init_db
from routers.analyze import router as analyze_router

app = FastAPI(
    title="Interview Coach API",
    description="Local AI-powered mock interview feedback system",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS — allow the React dev server
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite default
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: ensure temp/ and reports/ directories exist
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    ensure_dirs()
    init_db()


# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------
app.include_router(analyze_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "interview-coach-api"}
