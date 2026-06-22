"""
VidScholar Backend - Video Schemas
================================================
Pydantic models defining the shape of requests and responses for the
/api/videos endpoints. Keeping these separate from the SQLAlchemy
models (app/db/models/video.py) follows the standard FastAPI pattern:
DB models describe storage, schemas describe the API contract — they
are allowed to diverge (e.g. a schema can omit internal fields).
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.youtube_utils import extract_video_id, InvalidYouTubeURLError


class ProcessingStatus(str, Enum):
    """Lifecycle states for a video as it moves through the pipeline."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoProcessRequest(BaseModel):
    """Request body for POST /api/videos/process"""
    url: str = Field(
        ...,
        min_length=3,
        description="A full YouTube URL or a bare 11-character video ID.",
        examples=["https://www.youtube.com/watch?v=dQw4w9WgXcQ"],
    )

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, value: str) -> str:
        """
        Validates the URL at the schema layer so malformed input is
        rejected with a clean 422 before it ever reaches the service layer.
        We don't store the extracted ID here — the router calls
        extract_video_id again where it's actually needed — this validator
        exists purely to fail fast on garbage input.
        """
        try:
            extract_video_id(value)
        except InvalidYouTubeURLError as exc:
            raise ValueError(str(exc))
        return value


class VideoResponse(BaseModel):
    """Full representation of a processed video, returned by GET endpoints."""
    id: int
    video_id: str
    url: str
    title: Optional[str] = None
    channel_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: ProcessingStatus
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # allows `.model_validate(orm_instance)`


class VideoProcessResponse(BaseModel):
    """Immediate response returned right after POST /api/videos/process."""
    id: int
    video_id: str
    status: ProcessingStatus
    message: str


class VideoStatusResponse(BaseModel):
    """Lightweight response for polling GET /api/videos/{id}/status."""
    id: int
    video_id: str
    status: ProcessingStatus
    error_message: Optional[str] = None
    chunk_count: Optional[int] = None
