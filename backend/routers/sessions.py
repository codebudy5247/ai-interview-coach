import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.session_model import InterviewSession
from models.schemas import (
    SessionSummary,
    SessionDetail,
    SessionListResponse,
    FeedbackResponse,
    FeedbackScore,
    CleanupResponse,
)
from services.imagekit_service import delete_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    search: str = Query("", description="Filter by question text"),
    sort: str = Query("newest", description="Sort: newest | oldest | highest | lowest"),
    limit: int | None = Query(None, ge=1, le=500, description="Max sessions to return (default: all)"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    db: Session = Depends(get_db),
):
    """List saved sessions with optional search, sort, and pagination.

    `limit` is optional: when omitted, all matching sessions are returned
    (preserves the original behavior for clients that don't paginate).
    """
    query = db.query(InterviewSession)

    if search:
        query = query.filter(InterviewSession.question.ilike(f"%{search}%"))

    # Total count of all matches (before pagination)
    total = query.count()

    # Apply sorting
    if sort == "oldest":
        query = query.order_by(InterviewSession.created_at.asc())
    elif sort == "highest":
        query = query.order_by(InterviewSession.overall_score.desc())
    elif sort == "lowest":
        query = query.order_by(InterviewSession.overall_score.asc())
    else:  # newest (default)
        query = query.order_by(InterviewSession.created_at.desc())

    query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    sessions = query.all()

    # Build response with truncated questions
    session_summaries = []
    for s in sessions:
        # Truncate question for summary view
        truncated_question = s.question[:100] + "..." if len(s.question) > 100 else s.question
        session_summaries.append(
            SessionSummary(
                id=s.id,
                question=truncated_question,
                overall_score=s.overall_score,
                created_at=s.created_at.isoformat(),
            )
        )

    return SessionListResponse(sessions=session_summaries, total=total)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    """Get full session detail including feedback."""
    session = db.query(InterviewSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Parse feedback JSON
    feedback_data = json.loads(session.feedback_json)

    # Convert to FeedbackResponse model (include code-snippet fields)
    feedback = FeedbackResponse(
        overall_score=feedback_data["overall_score"],
        scores={k: FeedbackScore(score=v["score"], feedback=v["feedback"]) for k, v in feedback_data.get("scores", {}).items()},
        what_went_well=feedback_data.get("what_went_well", []),
        what_was_missed=feedback_data.get("what_was_missed", []),
        improvements=feedback_data.get("improvements", []),
        ideal_answer=feedback_data.get("ideal_answer", ""),
        ideal_code=feedback_data.get("ideal_code"),
        transcript=feedback_data.get("transcript", ""),
        audio_url=feedback_data.get("audio_url"),
        code_snippet=feedback_data.get("code_snippet"),
        code_language=feedback_data.get("code_language"),
    )

    return SessionDetail(
        id=session.id,
        question=session.question,
        transcript=session.transcript,
        overall_score=session.overall_score,
        feedback=feedback,
        created_at=session.created_at.isoformat(),
    )


@router.delete("/sessions/{session_id}", response_model=CleanupResponse)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a session from history."""
    session = db.query(InterviewSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract imagekit_file_id from feedback_json and delete remote file
    try:
        if session.feedback_json:
            feedback_data = json.loads(session.feedback_json)
            imagekit_file_id = feedback_data.get("imagekit_file_id")
            if imagekit_file_id:
                delete_audio(imagekit_file_id)
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Could not parse feedback_json for ImageKit cleanup: %s", e)
    except Exception as e:
        logger.warning("Failed to delete audio from ImageKit: %s", e)

    db.delete(session)
    db.commit()
    return CleanupResponse(success=True)