from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime
from database import Base


class InterviewSession(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)  # UUID session_id
    question = Column(Text, nullable=False)
    transcript = Column(Text, nullable=False)
    overall_score = Column(Integer, nullable=False)
    feedback_json = Column(Text, nullable=False)  # Full feedback as JSON string
    created_at = Column(DateTime, default=datetime.utcnow)