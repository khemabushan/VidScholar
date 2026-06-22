"""
VidScholar Backend - Database Session Management
================================================
Creates the SQLAlchemy engine and session factory from settings.DATABASE_URL,
and exposes:
  - `get_db()`: a FastAPI dependency that yields a session per-request and
     guarantees it's closed afterward (even if an exception occurs).
  - `init_db()`: creates all tables on startup if they don't already exist.
     Suitable for SQLite/dev. In a real production deployment with Postgres,
     this would typically be replaced by Alembic migrations.
"""

import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.db.base import Base

# Import all models here so Base.metadata is aware of every table before
# init_db() calls create_all(). New model modules added in later phases
# must be imported here too.
from app.db.models import video  # noqa: F401

logger = logging.getLogger("vidscholar")

# SQLite needs `check_same_thread=False` because FastAPI may use the
# connection across different async-handled threads. This flag is a no-op
# for other database backends (e.g. Postgres) so it's safe to always pass.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # set True temporarily for verbose SQL query debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Creates all tables defined on Base.metadata if they don't exist yet."""
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema ready.")


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency: provides a SQLAlchemy session for the lifetime of
    a single request, and ensures it's always closed afterward.

    Usage in a router:
        @router.get("/videos")
        def list_videos(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
