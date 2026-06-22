"""
VidScholar Backend - Video Router
================================================
Exposes the HTTP endpoints for submitting a YouTube URL, polling its
processing status, and listing/fetching/deleting processed videos.

The actual pipeline (fetch metadata -> fetch transcript -> chunk ->
embed -> store in Chroma) runs in a FastAPI BackgroundTask so the
POST /process call returns immediately with a "processing" status,
and the frontend polls GET /{id}/status until it flips to
"completed" or "failed". This avoids holding an HTTP connection open
for the entire duration of transcript fetching + embedding, which can
take anywhere from a few seconds to over a minute for long videos.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_youtube_service, get_transcript_service, get_vectorstore_service
from app.repositories.video_repository import VideoRepository
from app.schemas.video import (
    VideoProcessRequest,
    VideoProcessResponse,
    VideoResponse,
    VideoStatusResponse,
    ProcessingStatus,
)
from app.services.youtube_service import YouTubeService
from app.services.transcript_service import TranscriptService, TranscriptUnavailableError
from app.services.vectorstore_service import VectorStoreService
from app.utils.youtube_utils import extract_video_id, InvalidYouTubeURLError
from app.db.session import SessionLocal

logger = logging.getLogger("vidscholar")

router = APIRouter(prefix="/api/videos", tags=["Videos"])


def _run_processing_pipeline(video_row_id: int, video_id: str) -> None:
    """
    Executes the full ingestion pipeline for a video: fetch metadata,
    fetch transcript, chunk + embed + store in ChromaDB, then update the
    video's status in the database accordingly.

    Runs inside a BackgroundTask, so it opens its OWN database session
    rather than reusing the request-scoped one from `get_db()` (which
    will have already been closed by the time this function runs).
    """
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        video = repo.get_by_id(video_row_id)
        if video is None:
            logger.error(f"Background pipeline: video row {video_row_id} no longer exists.")
            return

        repo.update_status(video, ProcessingStatus.PROCESSING)

        # Step 1: best-effort metadata (title/channel/duration/thumbnail).
        youtube_service = YouTubeService()
        metadata = youtube_service.fetch_metadata(video_id)
        repo.update_metadata(
            video,
            title=metadata.title,
            channel_name=metadata.channel_name,
            thumbnail_url=metadata.thumbnail_url,
            duration_seconds=metadata.duration_seconds,
        )

        # Step 2: transcript fetch (required — failure here fails the video).
        transcript_service = TranscriptService()
        snippets = transcript_service.fetch_transcript(video_id)

        # Step 3: chunk + embed + store in ChromaDB.
        vectorstore_service = VectorStoreService()
        chunk_count = vectorstore_service.store_transcript(video_id, snippets)

        repo.update_status(
            video,
            ProcessingStatus.COMPLETED,
            chunk_count=chunk_count,
            chroma_collection_name=f"video_{video_id}",
        )
        logger.info(f"Video '{video_id}' processed successfully ({chunk_count} chunks).")

    except TranscriptUnavailableError as exc:
        logger.warning(f"Transcript unavailable for video '{video_id}': {exc}")
        _mark_failed(video_row_id, str(exc))
    except Exception as exc:  # noqa: BLE001 - top-level pipeline guard
        logger.exception(f"Unexpected error processing video '{video_id}': {exc}")
        _mark_failed(video_row_id, "An unexpected error occurred while processing this video.")
    finally:
        db.close()


def _mark_failed(video_row_id: int, error_message: str) -> None:
    """Helper to mark a video as failed using a fresh DB session, called
    from within exception handlers in _run_processing_pipeline above."""
    db = SessionLocal()
    try:
        repo = VideoRepository(db)
        video = repo.get_by_id(video_row_id)
        if video is not None:
            repo.update_status(video, ProcessingStatus.FAILED, error_message=error_message)
    finally:
        db.close()


@router.post(
    "/process",
    response_model=VideoProcessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_video(
    payload: VideoProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Accepts a YouTube URL, creates (or reuses) a video record, and kicks
    off background processing (metadata + transcript + embedding).
    Returns immediately with status "processing" — poll GET /{id}/status
    for completion.
    """
    try:
        video_id = extract_video_id(payload.url)
    except InvalidYouTubeURLError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    repo = VideoRepository(db)
    existing = repo.get_by_video_id(video_id)

    if existing is not None and existing.status == ProcessingStatus.COMPLETED:
        # Already fully processed — no need to redo the work. The user can
        # explicitly delete + re-add if they want a forced refresh.
        return VideoProcessResponse(
            id=existing.id,
            video_id=existing.video_id,
            status=existing.status,
            message="This video has already been processed.",
        )

    if existing is not None:
        # Previously failed or stuck mid-processing — reset and retry.
        video = existing
        repo.update_status(video, ProcessingStatus.PENDING, error_message=None)
    else:
        video = repo.create(video_id=video_id, url=payload.url)

    background_tasks.add_task(_run_processing_pipeline, video.id, video_id)

    return VideoProcessResponse(
        id=video.id,
        video_id=video.video_id,
        status=ProcessingStatus.PROCESSING,
        message="Video processing started. Poll /api/videos/{id}/status for updates.",
    )


@router.get("/{video_row_id}/status", response_model=VideoStatusResponse)
def get_video_status(video_row_id: int, db: Session = Depends(get_db)):
    """Lightweight polling endpoint for the frontend to check processing progress."""
    repo = VideoRepository(db)
    video = repo.get_by_id(video_row_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    return VideoStatusResponse(
        id=video.id,
        video_id=video.video_id,
        status=video.status,
        error_message=video.error_message,
        chunk_count=video.chunk_count,
    )


@router.get("/{video_row_id}", response_model=VideoResponse)
def get_video(video_row_id: int, db: Session = Depends(get_db)):
    """Returns the full record for a single processed video."""
    repo = VideoRepository(db)
    video = repo.get_by_id(video_row_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")
    return VideoResponse.model_validate(video)


@router.get("", response_model=list[VideoResponse])
def list_videos(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    """Returns recently processed videos, most recent first."""
    repo = VideoRepository(db)
    videos = repo.list_all(limit=limit, offset=offset)
    return [VideoResponse.model_validate(v) for v in videos]


@router.delete("/{video_row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_row_id: int,
    db: Session = Depends(get_db),
    vectorstore_service: VectorStoreService = Depends(get_vectorstore_service),
):
    """Deletes a video's database record AND its ChromaDB collection."""
    repo = VideoRepository(db)
    video = repo.get_by_id(video_row_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    vectorstore_service.delete_collection(video.video_id)
    repo.delete(video)
    return None
