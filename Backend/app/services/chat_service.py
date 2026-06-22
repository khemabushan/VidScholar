"""
VidScholar Backend - Chat Service
================================================
Implements the RAG (Retrieval-Augmented Generation) pipeline for the
"Chat With Video" feature:

  1. Retrieve the top_k most relevant transcript chunks for the user's
     question from this video's ChromaDB collection.
  2. Build a strict, grounding-only prompt that instructs the model to
     answer ONLY from the supplied transcript excerpts.
  3. Call OpenAI's chat completion endpoint (streaming or non-streaming).
  4. Return the answer alongside the exact chunks used as citations.

Hallucination-prevention strategy (the part of this file that matters
most):
  - If retrieval finds nothing relevant, we never call the LLM with an
    empty/weak context — we short-circuit and return a fixed
    "not covered in this video" response. An LLM given no context but
    still asked to answer will often guess; we remove that option
    entirely rather than trust a system prompt to prevent it.
  - A relevance threshold filters out chunks that are too dissimilar to
    the question (low cosine similarity) before they ever reach the
    prompt, since "top_k" alone always returns *something*, even when
    nothing in the video is actually relevant.
  - The system prompt explicitly forbids using outside knowledge and
    explicitly requires the model to say it doesn't know rather than
    speculate, with the refusal phrase given verbatim so we can detect
    it and set `grounded=False` for the frontend.
  - Each context excerpt is labeled with its timestamp so the model is
    encouraged to ground specific claims to specific moments, and so we
    can show citations the person can actually verify against the video.
"""

import logging
from typing import AsyncGenerator, List, Optional

from openai import OpenAI, AsyncOpenAI

from app.core.config import settings
from app.schemas.chat import Citation, ChatHistoryMessage
from app.services.vectorstore_service import VectorStoreService, RetrievedChunk

logger = logging.getLogger("vidscholar")

# Returned verbatim when no relevant context is found, OR detected in the
# model's own output, so the frontend can render a distinct "not covered"
# state instead of a normal answer bubble.
NO_CONTEXT_ANSWER = (
    "I couldn't find anything in this video's transcript that answers that "
    "question. Try rephrasing, or ask about a topic that's actually "
    "covered in the video."
)

# Chroma's relevance_score (computed in vectorstore_service.py as
# 1 - distance) ranges roughly 0-1, higher = more similar. Chunks below
# this threshold are treated as "not actually relevant" and dropped
# before reaching the prompt, even if top_k would otherwise include them.
MIN_RELEVANCE_SCORE = 0.05

SYSTEM_PROMPT_TEMPLATE = """You are VidScholar's video assistant. You answer questions \
using ONLY the transcript excerpts provided below, which come from a single YouTube video.

STRICT RULES (do not break these under any circumstances):
1. Use ONLY the information in the "TRANSCRIPT EXCERPTS" section to answer. \
Do not use any outside knowledge, training data, or assumptions about the topic.
2. If the excerpts contain partial information related to the question,
answer using that information and clearly state any limitations.

3. Only return:
"{no_context_answer}"
when the excerpts contain no relevant information at all.
4. Never invent, guess, or extrapolate facts, numbers, names, or claims that \
are not explicitly stated in the excerpts.
5. Keep answers concise but provide examples or summaries when they are directly supported by the transcript.
6. Keep answers concise and directly responsive to the question asked.

TRANSCRIPT EXCERPTS:
{context_block}
"""


def _build_context_block(chunks: List[RetrievedChunk]) -> str:
    """Formats retrieved chunks into a labeled block for the system prompt,
    each excerpt tagged with its timestamp so the model can cite it."""
    if not chunks:
        return "(no relevant excerpts found)"

    parts = []
    for chunk in chunks:
        parts.append(f"[{chunk.timestamp_label}] {chunk.text}")
    return "\n\n".join(parts)


def _chunk_to_citation(chunk: RetrievedChunk) -> Citation:
    return Citation(
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        start_time=chunk.start_time,
        end_time=chunk.end_time,
        timestamp_label=chunk.timestamp_label,
        timestamped_url=chunk.timestamped_url,
        relevance_score=chunk.relevance_score,
    )


class ChatService:
    """Orchestrates retrieval + grounded generation for video chat."""

    def __init__(self, vectorstore_service: VectorStoreService) -> None:
        self._vectorstore_service = vectorstore_service
        self._openai_client = (
            OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        )
        # A separate AsyncOpenAI client is used specifically for the
        # streaming path (ask_stream below). The sync OpenAI client's
        # streaming iterator is a blocking generator under the hood;
        # iterating it inside an `async def` with a plain `for` would
        # block the event loop between tokens rather than yielding
        # control, which defeats the purpose of streaming in an async
        # web server. AsyncOpenAI's stream is natively awaitable/async-
        # iterable, so `async for` here genuinely yields control back to
        # FastAPI between tokens.
        self._async_openai_client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        )

    # ------------------------------------------------------------------
    # Retrieval + filtering
    # ------------------------------------------------------------------
    def _retrieve_relevant_chunks(
        self, video_id: str, question: str, top_k: int
    ) -> List[RetrievedChunk]:
        """
        Retrieves the top_k most similar chunks, then drops any below
        MIN_RELEVANCE_SCORE. This second filter is what actually prevents
        hallucination on off-topic questions: vector search always
        returns *some* result for *any* query, however unrelated, so
        top_k alone cannot signal "nothing relevant exists."
        """
        chunks = self._vectorstore_service.query(video_id, question, top_k=top_k)


        print("\n===== SCORES =====")

        for c in chunks:
            print(c.relevance_score)

        print("==================\n")
        relevant = [c for c in chunks if c.relevance_score >= MIN_RELEVANCE_SCORE]

        if len(relevant) < len(chunks):
            logger.info(
                f"Filtered {len(chunks) - len(relevant)} low-relevance chunk(s) "
                f"below threshold {MIN_RELEVANCE_SCORE} for video '{video_id}'."
            )
        return relevant

    def _build_messages(
        self,
        question: str,
        context_chunks: List[RetrievedChunk],
        history: Optional[List[ChatHistoryMessage]],
    ) -> List[dict]:
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            no_context_answer=NO_CONTEXT_ANSWER,
            context_block=_build_context_block(context_chunks),
        )

        messages: List[dict] = [{"role": "system", "content": system_prompt}]

        # Prior turns are included for conversational continuity (e.g.
        # "what about earlier in the video?" following on from a previous
        # answer), but we deliberately do NOT re-run retrieval for them —
        # only the current turn's question drives what context is injected,
        # keeping the grounding behavior predictable per-turn.
        if history:
            for turn in history[-10:]:  # cap history to keep prompts bounded
                messages.append({"role": turn.role, "content": turn.content})

        messages.append({"role": "user", "content": question})
        return messages

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------
    def ask(
        self,
        video_id: str,
        question: str,
        top_k: int = 5,
        history: Optional[List[ChatHistoryMessage]] = None,
    ) -> tuple[str, List[Citation], bool]:
        """
        Runs the full RAG pipeline and returns (answer, citations, grounded).
        `grounded` is False when no relevant context was found at all —
        in that case we skip calling the LLM entirely and return the fixed
        NO_CONTEXT_ANSWER, which is the strongest hallucination guard
        available: the model is never given the chance to improvise an
        answer it has no basis for.
        """
        if self._openai_client is None:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in your .env file "
                "before using the chat feature."
            )

        relevant_chunks = self._retrieve_relevant_chunks(video_id, question, top_k)

        if not relevant_chunks:
            return NO_CONTEXT_ANSWER, [], False

        messages = self._build_messages(question, relevant_chunks, history)

        response = self._openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.2,  # low temperature: favors faithful grounding over creative phrasing
        )
        answer = (response.choices[0].message.content or "").strip()

        citations = [_chunk_to_citation(c) for c in relevant_chunks]

        # The model may still follow rule #2 and emit the fixed refusal
        # sentence verbatim even though we found *some* relevant-scoring
        # chunks (e.g. they were tangentially related but didn't actually
        # answer the question). Detect that case and drop citations too,
        # since they weren't actually used to support a real answer.
        grounded = NO_CONTEXT_ANSWER not in answer
        if not grounded:
            citations = []

        return answer, citations, grounded

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    async def ask_stream(
        self,
        video_id: str,
        question: str,
        top_k: int = 5,
        history: Optional[List[ChatHistoryMessage]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator yielding the answer token-by-token, for use with
        FastAPI's StreamingResponse. Uses AsyncOpenAI so each token is
        genuinely yielded to the event loop as it arrives, rather than
        blocking it. The caller is responsible for retrieving citations
        separately (via get_citations_for_question) if it needs to send
        them as a final SSE event — see api/routers/chat.py.
        """
        if self._async_openai_client is None:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Set it in your .env file "
                "before using the chat feature."
            )

        relevant_chunks = self._retrieve_relevant_chunks(video_id, question, top_k)

        if not relevant_chunks:
            yield NO_CONTEXT_ANSWER
            return

        messages = self._build_messages(question, relevant_chunks, history)

        stream = await self._async_openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.2,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    def get_citations_for_question(
        self, video_id: str, question: str, top_k: int = 5
    ) -> List[Citation]:
        """
        Public helper so the streaming router can fetch the same citation
        set used to build the prompt, without duplicating the relevance
        filtering logic. Safe to call twice (once implicitly inside
        ask_stream, once here) since retrieval is read-only and
        deterministic for a fixed question/top_k.
        """
        relevant_chunks = self._retrieve_relevant_chunks(video_id, question, top_k)
        return [_chunk_to_citation(c) for c in relevant_chunks]
