"""
VidScholar Backend - Vector Store Service
================================================
Owns all interaction with ChromaDB and OpenAI embeddings:
  - Chunking a transcript and embedding each chunk via OpenAI's
    embeddings API (text-embedding-3-small by default).
  - Storing chunks + metadata (start/end timestamps, chunk index) in a
    per-video ChromaDB collection, so each video's vectors are isolated
    and easy to delete/re-process independently.
  - Querying a video's collection for the most relevant chunks given a
    natural-language question (used by chat_service.py in Phase 4).

Design note: we deliberately do NOT use ChromaDB's built-in default
embedding function (which downloads an ONNX model from the network at
runtime). Instead we compute embeddings ourselves via the OpenAI API
and pass them to Chroma explicitly. This matches our specified tech
stack (OpenAI for embeddings) and avoids an extra uncontrolled network
dependency at query time.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

import chromadb
from chromadb.api.models.Collection import Collection
from openai import OpenAI

from app.core.config import settings
from app.utils.text_splitter import TranscriptSnippet, TranscriptChunk, chunk_transcript
from app.utils.timestamp_formatter import format_seconds_to_timestamp, build_timestamped_url

logger = logging.getLogger("vidscholar")


@dataclass
class RetrievedChunk:
    """A single chunk returned from a similarity search, with everything
    a caller needs to display it and cite its source timestamp."""
    text: str
    start_time: float
    end_time: float
    timestamp_label: str
    timestamped_url: str
    chunk_index: int
    relevance_score: float


def _collection_name_for_video(video_id: str) -> str:
    """
    Derives a deterministic, Chroma-safe collection name from a video ID.
    Chroma collection names must be 3-63 characters; our prefix + 11-char
    video ID comfortably fits that constraint.
    """
    return f"video_{video_id}"


class VectorStoreService:
    """Handles chunking, embedding, storing, and querying transcript vectors."""

    def __init__(self) -> None:
        self._chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Calls OpenAI's embeddings endpoint for a batch of texts and returns
        one embedding vector per input text, in the same order.
        """
        if self._openai_client is None:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in your .env file "
                "before processing videos."
            )

        response = self._openai_client.embeddings.create(
            input=texts,
            model=settings.OPENAI_EMBEDDING_MODEL,
        )
        # OpenAI guarantees response.data is returned in the same order
        # as the input list, so a simple list comprehension preserves alignment.
        return [item.embedding for item in response.data]

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------
    def _get_or_create_collection(self, video_id: str) -> Collection:
        return self._chroma_client.get_or_create_collection(
            name=_collection_name_for_video(video_id),
            metadata={"video_id": video_id},
        )

    def collection_exists(self, video_id: str) -> bool:
        """Checks whether a collection has already been created for this video."""
        existing_names = {c.name for c in self._chroma_client.list_collections()}
        return _collection_name_for_video(video_id) in existing_names

    def delete_collection(self, video_id: str) -> None:
        """Removes all stored vectors for a video, e.g. before re-processing it."""
        name = _collection_name_for_video(video_id)
        try:
            self._chroma_client.delete_collection(name=name)
            logger.info(f"Deleted Chroma collection '{name}'.")
        except Exception as exc:  # noqa: BLE001 - collection may simply not exist yet
            logger.debug(f"Could not delete collection '{name}' (may not exist): {exc}")

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def store_transcript(
        self,
        video_id: str,
        snippets: List[TranscriptSnippet],
        max_chunk_chars: int = 1000,
        embedding_batch_size: int = 100,
    ) -> int:
        """
        Chunks the given transcript snippets, embeds each chunk, and stores
        them in this video's ChromaDB collection. Any pre-existing
        collection for this video is wiped first, so re-processing a video
        is always idempotent rather than appending duplicates.

        Returns:
            The number of chunks stored.
        """
        # Always start fresh: avoids duplicate/stale vectors if this video
        # was processed before (e.g. user re-submits the same URL).
        self.delete_collection(video_id)
        collection = self._get_or_create_collection(video_id)

        chunks: List[TranscriptChunk] = chunk_transcript(snippets, max_chunk_chars=max_chunk_chars)
        if not chunks:
            logger.warning(f"No chunks produced for video '{video_id}'; nothing to store.")
            return 0

        total_stored = 0
        for batch_start in range(0, len(chunks), embedding_batch_size):
            batch = chunks[batch_start: batch_start + embedding_batch_size]
            batch_texts = [c.text for c in batch]

            embeddings = self._embed_texts(batch_texts)

            ids = [f"{video_id}_chunk_{c.chunk_index}" for c in batch]
            metadatas = [
                {
                    "video_id": video_id,
                    "chunk_index": c.chunk_index,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                }
                for c in batch
            ]

            collection.add(
                ids=ids,
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_stored += len(batch)
            logger.info(
                f"Stored batch of {len(batch)} chunks for video '{video_id}' "
                f"({total_stored}/{len(chunks)} total)."
            )

        return total_stored
    
    def get_all_chunks(self, video_id: str):
        """
        Returns all transcript chunks for a video,
        sorted by chunk_index.
        """

        if not self.collection_exists(video_id):
            return []

        collection = self._get_or_create_collection(video_id)

        results = collection.get(
            include=["documents", "metadatas"]
        )

        chunks = []

        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        for document, metadata in zip(documents, metadatas):

            if metadata.get("video_id") != video_id:
                continue

            chunks.append(
                {
                    "text": document,
                    "chunk_index": metadata.get("chunk_index", 0),
                    "start_time": metadata.get("start_time", 0),
                    "end_time": metadata.get("end_time", 0),
                }
            )

        chunks.sort(key=lambda x: x["chunk_index"])

        return chunks

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def query(
        self,
        video_id: str,
        query_text: str,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Embeds `query_text` and returns the top_k most similar chunks
        stored for this video, each enriched with a human-readable
        timestamp label and a clickable timestamped YouTube URL.
        """
        if not self.collection_exists(video_id):
            logger.warning(f"No collection exists for video '{video_id}'; returning no results.")
            return []

        collection = self._get_or_create_collection(video_id)
        query_embedding = self._embed_texts([query_text])[0]

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        retrieved: List[RetrievedChunk] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc_text, metadata, distance in zip(documents, metadatas, distances):
            start_time = float(metadata.get("start_time", 0.0))
            end_time = float(metadata.get("end_time", start_time))
            retrieved.append(
                RetrievedChunk(
                    text=doc_text,
                    start_time=start_time,
                    end_time=end_time,
                    timestamp_label=format_seconds_to_timestamp(start_time),
                    timestamped_url=build_timestamped_url(video_id, start_time),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    # Chroma returns a distance (lower = more similar) by
                    # default for cosine/L2 space; we convert to an
                    # intuitive 0-1 "relevance" style score for the UI.
                   relevance_score=1 / (1 + distance),
                )
            )

        return retrieved
