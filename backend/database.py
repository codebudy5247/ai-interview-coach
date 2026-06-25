from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DB_PATH = Path(__file__).parent / "interview_coach.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session, auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist."""
    # Import all models to register them with Base.metadata
    from models import session_model  # noqa: F401  (registers the ORM table)
    Base.metadata.create_all(bind=engine)

    # create_all won't add indexes to a pre-existing table, so ensure them
    # explicitly and idempotently for already-created databases.
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sessions_created_at ON sessions (created_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_sessions_overall_score ON sessions (overall_score)"
        ))