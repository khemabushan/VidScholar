"""
VidScholar Backend - Video ORM Model
================================================
SQLAlchemy model representing a single processed YouTube video and its
pipeline status. This is the source of truth for video metadata; the
actual transcript text/embeddings live in ChromaDB (see
vectorstore_service.py), keyed by this row's `video_id`.
"""

from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.schemas.video import ProcessingStatus


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp factory, used for created_at/updated_at."""
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # The 11-character YouTube video ID, unique per video.
    video_id: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)

    # Original URL as submitted by the user (kept for display/debugging).
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Tracks where this video is in the processing pipeline.
    status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, native_enum=False, length=20),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )

    # Populated only if status == FAILED, so the frontend can show why.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Number of vector chunks stored in ChromaDB for this video, useful
    # for debugging/diagnostics and for the status polling endpoint.
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # The name of the ChromaDB collection holding this video's vectors.
    # Stored explicitly rather than always re-deriving it, in case the
    # naming convention ever changes — old rows stay valid.
    chroma_collection_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper only
        return f"<Video id={self.id} video_id={self.video_id} status={self.status}>"
