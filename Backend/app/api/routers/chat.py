"""
VidScholar Backend - Chat Router
================================================
Exposes the "Chat With Video" HTTP endpoints:

  - POST /api/videos/{id}/chat         non-streaming, returns full JSON
  - POST /api/videos/{id}/chat/stream  streaming via Server-Sent Events

Both endpoints require the target video to exist AND have status
"completed" (i.e. its transcript has actually been chunked and
embedded into ChromaDB) — chatting against a video that's still
processing or that failed would have nothing to retrieve from, so we
reject that case early with a clear error rather than silently
returning a "no context" answer that looks like a real response.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_chat_service
from app.repositories.video_repository import VideoRepository
from app.schemas.video import ProcessingStatus
from app.schemas.chat import ChatMessageWithHistoryRequest, ChatMessageResponse
from app.services.chat_service import ChatService, NO_CONTEXT_ANSWER

logger = logging.getLogger("vidscholar")

router = APIRouter(prefix="/api/videos", tags=["Chat"])


def _get_ready_video(video_row_id: int, db: Session):
    """
    Shared lookup + readiness check used by both chat endpoints. Raises
    a 404 if the video doesn't exist, or a 409 if it exists but hasn't
    finished processing (or failed), since there is nothing to chat
    against in either case.
    """
    repo = VideoRepository(db)
    video = repo.get_by_id(video_row_id)
    if video is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found.")

    if video.status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This video's status is '{video.status.value}'. "
                "Chat is only available once processing has completed."
            ),
        )
    return video


@router.post("/{video_row_id}/chat", response_model=ChatMessageResponse)
def chat_with_video(
    video_row_id: int,
    payload: ChatMessageWithHistoryRequest,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Non-streaming chat endpoint: retrieves relevant transcript chunks,
    asks OpenAI to answer using only that context, and returns the full
    answer plus the citations that grounded it in a single JSON response.
    """
    video = _get_ready_video(video_row_id, db)

    try:
        answer, citations, grounded = chat_service.ask(
            video_id=video.video_id,
            question=payload.message,
            top_k=payload.top_k,
            history=payload.history,
        )
    except RuntimeError as exc:
        # Raised by ChatService when OPENAI_API_KEY is missing — a
        # configuration error, not a user error, so 503 rather than 400.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return ChatMessageResponse(answer=answer, citations=citations, grounded=grounded)


@router.post("/{video_row_id}/chat/stream")
def chat_with_video_stream(
    video_row_id: int,
    payload: ChatMessageWithHistoryRequest,
    db: Session = Depends(get_db),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Streaming chat endpoint using Server-Sent Events. Emits a sequence of
    events as plain `data: <json>\\n\\n` lines:

      - One or more {"type": "token", "content": "..."} events as the
        answer streams in from OpenAI, in real time as each token arrives
        (this is a true async generator passed straight to
        StreamingResponse — no buffering, no eager collection).
      - Exactly one final {"type": "done", "citations": [...], "grounded": bool}
        event once the stream completes, carrying the citation list the
        frontend needs to render timestamp badges.
      - On error, a single {"type": "error", "detail": "..."} event.

    The frontend (useChat.ts) parses this with a fetch-stream reader
    rather than EventSource, since EventSource cannot send a POST body
    or custom headers.
    """
    video = _get_ready_video(video_row_id, db)

    async def event_stream() -> AsyncGenerator[str, None]:
        full_answer_parts: list[str] = []
        try:
            # `async for` directly over ChatService.ask_stream means each
            # token is forwarded to the client the instant OpenAI emits
            # it — there is no intermediate buffering step here.
            async for token in chat_service.ask_stream(
                video_id=video.video_id,
                question=payload.message,
                top_k=payload.top_k,
                history=payload.history,
            ):
                full_answer_parts.append(token)
                yield _sse_event({"type": "token", "content": token})

            full_answer = "".join(full_answer_parts)

            # Re-fetch the citation set used for this question. Retrieval
            # is deterministic for a fixed (video_id, question, top_k), so
            # this matches exactly what grounded the streamed answer above.
            citations = chat_service.get_citations_for_question(
                video.video_id, payload.message, payload.top_k
            )

            grounded = NO_CONTEXT_ANSWER not in full_answer
            if not grounded:
                citations = []

            yield _sse_event(
                {
                    "type": "done",
                    "citations": [c.model_dump() for c in citations],
                    "grounded": grounded,
                }
            )
        except RuntimeError as exc:
            yield _sse_event({"type": "error", "detail": str(exc)})
        except Exception as exc:  # noqa: BLE001 - last-resort guard so the stream always terminates cleanly
            logger.exception(
                f"Unexpected error during chat stream for video '{video.video_id}': {exc}"
            )
            yield _sse_event(
                {"type": "error", "detail": "An unexpected error occurred while generating the answer."}
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disables proxy buffering (e.g. nginx) so tokens arrive promptly
        },
    )


def _sse_event(data: dict) -> str:
    """Formats a dict as a single Server-Sent Event line."""
    return f"data: {json.dumps(data)}\n\n"
