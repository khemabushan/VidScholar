"""
VidScholar Backend - Video Repository
================================================
Encapsulates all direct database queries for the Video model. Services
(e.g. youtube_service.py, transcript_service.py) call into this
repository instead of writing raw SQLAlchemy queries themselves. This
keeps persistence concerns isolated and makes it trivial to swap the
underlying storage later without touching business logic.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.video import Video
from app.schemas.video import ProcessingStatus


class VideoRepository:
    """All read/write operations for the `videos` table, given a Session."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, video_row_id: int) -> Optional[Video]:
        """Fetch a video row by its internal primary key (not the YouTube ID)."""
        return self.db.query(Video).filter(Video.id == video_row_id).first()

    def get_by_video_id(self, video_id: str) -> Optional[Video]:
        """Fetch a video row by its YouTube video_id (the 11-char string)."""
        return self.db.query(Video).filter(Video.video_id == video_id).first()

    def create(self, video_id: str, url: str) -> Video:
        """Inserts a new pending video row and returns it (with id populated)."""
        video = Video(
            video_id=video_id,
            url=url,
            status=ProcessingStatus.PENDING,
        )
        self.db.add(video)
        self.db.commit()
        self.db.refresh(video)
        return video

    def update_metadata(
        self,
        video: Video,
        title: Optional[str] = None,
        channel_name: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ) -> Video:
        """Updates descriptive metadata fields fetched from YouTube."""
        if title is not None:
            video.title = title
        if channel_name is not None:
            video.channel_name = channel_name
        if thumbnail_url is not None:
            video.thumbnail_url = thumbnail_url
        if duration_seconds is not None:
            video.duration_seconds = duration_seconds
        self.db.commit()
        self.db.refresh(video)
        return video

    def update_status(
        self,
        video: Video,
        status: ProcessingStatus,
        error_message: Optional[str] = None,
        chunk_count: Optional[int] = None,
        chroma_collection_name: Optional[str] = None,
    ) -> Video:
        """Transitions a video's pipeline status, optionally recording an
        error message (on failure) or chunk count / collection name
        (on success)."""
        video.status = status
        if error_message is not None:
            video.error_message = error_message
        if chunk_count is not None:
            video.chunk_count = chunk_count
        if chroma_collection_name is not None:
            video.chroma_collection_name = chroma_collection_name
        self.db.commit()
        self.db.refresh(video)
        return video

    def list_all(self, limit: int = 50, offset: int = 0) -> list[Video]:
        """Returns the most recently created videos, paginated."""
        return (
            self.db.query(Video)
            .order_by(Video.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete(self, video: Video) -> None:
        """Removes a video row. Caller is responsible for also deleting
        its corresponding ChromaDB collection (see vectorstore_service.py)."""
        self.db.delete(video)
        self.db.commit()
