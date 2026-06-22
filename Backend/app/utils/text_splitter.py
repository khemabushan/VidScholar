"""
VidScholar Backend - Transcript Text Splitter
================================================
Splits a list of raw transcript snippets (each with text + start time +
duration) into larger, semantically-coherent chunks suitable for
embedding, WITHOUT losing the start-timestamp of each chunk.

Why not just use LangChain's RecursiveCharacterTextSplitter directly?
Because that splitter operates on a single plain string and discards
position information. We need to know which timestamp each resulting
chunk started at, so we roll our own lightweight greedy chunker that
accumulates snippets up to a target character size and records the
start time of the first snippet in each chunk.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class TranscriptSnippet:
    """Mirrors youtube_transcript_api's FetchedTranscriptSnippet shape,
    decoupled from that library so services don't import it directly."""
    text: str
    start: float
    duration: float = 0.0


@dataclass
class TranscriptChunk:
    """A merged group of snippets, ready to be embedded as one vector."""
    text: str
    start_time: float
    end_time: float
    chunk_index: int
    snippet_count: int = field(default=0)


def chunk_transcript(
    snippets: List[TranscriptSnippet],
    max_chunk_chars: int = 1000,
    chunk_overlap_snippets: int = 1,
) -> List[TranscriptChunk]:
    """
    Greedily merges consecutive transcript snippets into chunks of roughly
    `max_chunk_chars` characters each. Each chunk records the start_time of
    its first snippet and the end_time (start + duration) of its last
    snippet, so we can cite an exact moment in the video later.

    Args:
        snippets: ordered list of transcript snippets from the video.
        max_chunk_chars: soft cap on characters per chunk before starting a new one.
        chunk_overlap_snippets: how many trailing snippets from the previous
            chunk to repeat at the start of the next chunk, for better
            retrieval context continuity (similar in spirit to LangChain's
            chunk_overlap but snippet-based instead of character-based).

    Returns:
        List of TranscriptChunk objects, in original video order.
    """
    if not snippets:
        return []

    chunks: List[TranscriptChunk] = []
    current_texts: List[str] = []
    current_snippets: List[TranscriptSnippet] = []
    current_char_count = 0
    chunk_index = 0

    def flush_chunk() -> None:
        nonlocal current_texts, current_snippets, current_char_count, chunk_index
        if not current_snippets:
            return
        first = current_snippets[0]
        last = current_snippets[-1]
        chunks.append(
            TranscriptChunk(
                text=" ".join(current_texts).strip(),
                start_time=first.start,
                end_time=last.start + (last.duration or 0.0),
                chunk_index=chunk_index,
                snippet_count=len(current_snippets),
            )
        )
        chunk_index += 1

    for snippet in snippets:
        cleaned_text = snippet.text.strip().replace("\n", " ")
        if not cleaned_text:
            continue

        # If adding this snippet would blow past the soft limit AND we
        # already have content, flush the current chunk first.
        if current_char_count + len(cleaned_text) > max_chunk_chars and current_texts:
            flush_chunk()

            # Apply overlap: carry forward the last N snippets so the next
            # chunk has some shared context with the previous one.
            overlap = current_snippets[-chunk_overlap_snippets:] if chunk_overlap_snippets > 0 else []
            current_texts = [s.text.strip().replace("\n", " ") for s in overlap]
            current_snippets = list(overlap)
            current_char_count = sum(len(t) for t in current_texts)

        current_texts.append(cleaned_text)
        current_snippets.append(snippet)
        current_char_count += len(cleaned_text)

    # Flush whatever remains after the loop ends.
    flush_chunk()

    return chunks
