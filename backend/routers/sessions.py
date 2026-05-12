from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.session_model import InterviewSession
from models.schemas import SessionSummary, SessionDetail, SessionListResponse, FeedbackResponse, FeedbackScore

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    search: str = Query("", description="Filter by question text"),
    sort: str = Query("newest", description="Sort: newest | oldest | highest | lowest"),
    db: Session = Depends(get_db),
):
    """List all saved sessions with optional search and sort."""
    query = db.query(InterviewSession)

    if search:
        query = query.filter(InterviewSession.question.ilike(f"%{search}%"))

    # Apply sorting
    if sort == "newest":
        query = query.order_by(InterviewSession.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(InterviewSession.created_at.asc())
    elif sort == "highest":
        query = query.order_by(InterviewSession.overall_score.desc())
    elif sort == "lowest":
        query = query.order_by(InterviewSession.overall_score.asc())

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

    return SessionListResponse(sessions=session_summaries, total=len(session_summaries))


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    """Get full session detail including feedback."""
    session = db.query(InterviewSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Parse feedback JSON
    import json
    feedback_data = json.loads(session.feedback_json)

    # Convert to FeedbackResponse model
    feedback = FeedbackResponse(
        overall_score=feedback_data["overall_score"],
        scores={k: FeedbackScore(score=v["score"], feedback=v["feedback"]) for k, v in feedback_data.get("scores", {}).items()},
        what_went_well=feedback_data.get("what_went_well", []),
        what_was_missed=feedback_data.get("what_was_missed", []),
        improvements=feedback_data.get("improvements", []),
        ideal_answer=feedback_data.get("ideal_answer", ""),
        transcript=feedback_data.get("transcript", ""),
        audio_url=feedback_data.get("audio_url"),
    )

    return SessionDetail(
        id=session.id,
        question=session.question,
        transcript=session.transcript,
        overall_score=session.overall_score,
        feedback=feedback,
        created_at=session.created_at.isoformat(),
    )


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a session from history."""
    session = db.query(InterviewSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Extract imagekit_file_id from feedback_json and delete remote file
    try:
        import json
        from services.imagekit_service import delete_audio
        if session.feedback_json:
            feedback_data = json.loads(session.feedback_json)
            imagekit_file_id = feedback_data.get("imagekit_file_id")
            if imagekit_file_id:
                delete_audio(imagekit_file_id)
    except Exception as e:
        print(f"Failed to delete audio from ImageKit: {e}")

    db.delete(session)
    db.commit()
    return {"success": True}