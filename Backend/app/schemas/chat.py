"""
VidScholar Backend - Chat Schemas
================================================
Pydantic models defining the shape of requests and responses for the
/api/videos/{id}/chat endpoints. A "citation" here is a transcript
chunk that was actually used to ground the model's answer, surfaced
back to the frontend so it can render a clickable timestamp badge
(see CitationBadge.tsx).
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Request body for POST /api/videos/{id}/chat"""
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question about the video.",
        examples=["What does the speaker say about neural networks?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=15,
        description="How many transcript chunks to retrieve as context.",
    )


class Citation(BaseModel):
    """
    A single transcript chunk that was used as grounding context for an
    answer. chunk_index lets the frontend de-duplicate citations that
    point at the same underlying chunk across multiple chat turns.
    """
    chunk_index: int
    text: str
    start_time: float
    end_time: float
    timestamp_label: str
    timestamped_url: str
    relevance_score: float


class ChatMessageResponse(BaseModel):
    """
    Full (non-streaming) response body for POST /api/videos/{id}/chat.
    Used by the simple request/response flow; the streaming variant
    (text/event-stream) sends the same `citations` payload as a final
    SSE event after streaming the answer token-by-token.
    """
    answer: str
    citations: List[Citation]
    grounded: bool = Field(
        description=(
            "False when no relevant transcript context was found and the "
            "model was instructed to decline rather than guess, signaling "
            "the frontend to render the answer as an 'unable to answer' "
            "state rather than a normal grounded response."
        )
    )


class ChatHistoryMessage(BaseModel):
    """A single prior turn in the conversation, used to give the model
    short-term memory of the ongoing chat without re-retrieving context
    for earlier turns."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatMessageWithHistoryRequest(ChatMessageRequest):
    """
    Extended request variant that includes prior conversation turns.
    Kept as a separate schema (rather than always requiring history on
    ChatMessageRequest) so the simplest possible request body still works
    for single-turn callers/tests.
    """
    history: Optional[List[ChatHistoryMessage]] = Field(
        default=None,
        description="Prior turns in this chat session, oldest first.",
    )
