from pydantic import BaseModel
from typing import Dict, List, Optional


class AnalyzeResponse(BaseModel):
    session_id: str


class FeedbackScore(BaseModel):
    score: int          # 1–10
    feedback: str       # explanation


class FeedbackResponse(BaseModel):
    overall_score: int
    scores: Dict[str, FeedbackScore]   # correctness, clarity, structure, relevance
    what_went_well: List[str]
    what_was_missed: List[str]
    improvements: List[str]
    ideal_answer: str
    transcript: str                    # original Whisper transcript
    audio_url: Optional[str] = None
    code_snippet: Optional[str] = None
    code_language: Optional[str] = None


class SSEEvent(BaseModel):
    step: str
    status: str     # pending | in_progress | done | error
    message: str


class CleanupResponse(BaseModel):
    success: bool


class SessionSummary(BaseModel):
    """Lightweight session info for the history list."""
    id: str
    question: str  # truncated for display
    overall_score: int
    created_at: str  # ISO 8601 datetime string


class SessionDetail(BaseModel):
    """Full session data for the detail view."""
    id: str
    question: str
    transcript: str
    overall_score: int
    feedback: FeedbackResponse
    created_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]
    total: int
