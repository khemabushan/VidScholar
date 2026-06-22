"""
VidScholar Backend - Shared API Dependencies
================================================
Central place for FastAPI dependency-injection providers used across
multiple routers. Currently re-exports the DB session dependency and
provides singleton-style service factories so routers don't need to
instantiate services themselves on every request.
"""

from functools import lru_cache

from app.db.session import get_db  # noqa: F401 - re-exported for routers to import from one place
from app.services.youtube_service import YouTubeService
from app.services.transcript_service import TranscriptService
from app.services.vectorstore_service import VectorStoreService
from app.services.chat_service import ChatService


@lru_cache
def get_youtube_service() -> YouTubeService:
    """
    Returns a cached YouTubeService instance. Cached via lru_cache because
    the service is stateless and cheap to share across requests, avoiding
    repeated instantiation overhead.
    """
    return YouTubeService()


@lru_cache
def get_transcript_service() -> TranscriptService:
    """Returns a cached TranscriptService instance (stateless, safe to share)."""
    return TranscriptService()


@lru_cache
def get_vectorstore_service() -> VectorStoreService:
    """
    Returns a cached VectorStoreService instance. This holds the ChromaDB
    PersistentClient and OpenAI client, both of which are safe and
    efficient to reuse across requests rather than recreating per call.
    """
    return VectorStoreService()


@lru_cache
def get_chat_service() -> ChatService:
    """
    Returns a cached ChatService instance. Depends on the same cached
    VectorStoreService (via direct call rather than FastAPI's Depends,
    since lru_cache-decorated functions are plain functions here, not
    request-scoped) so both services share one ChromaDB/OpenAI client pair.
    """
    return ChatService(vectorstore_service=get_vectorstore_service())
