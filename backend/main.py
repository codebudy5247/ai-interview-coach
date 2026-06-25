import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from utils.file_handler import ensure_dirs
from database import init_db
from routers.analyze import router as analyze_router
from routers.sessions import router as sessions_router

# ---------------------------------------------------------------------------
# Logging — configure once for the whole app
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=config.LOG_LEVEL,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Interview Coach API",
    description="Local AI-powered mock interview feedback system",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS — origins configurable via CORS_ORIGINS (see config.py)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
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
app.include_router(sessions_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "interview-coach-api"}
