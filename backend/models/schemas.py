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


class SSEEvent(BaseModel):
    step: str
    status: str     # pending | in_progress | done | error
    message: str


class CleanupResponse(BaseModel):
    success: bool
