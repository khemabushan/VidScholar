"""
VidScholar Backend - Transcript Service
================================================
Wraps youtube-transcript-api (v1.x) to fetch a video's transcript with
per-line timestamps. Translates that library's exceptions into our own
domain exception (TranscriptUnavailableError) so callers (services,
routers) don't need to import or know about youtube-transcript-api
directly — keeping that third-party dependency isolated to this file.
"""

import logging
from typing import List
import requests
from app.core.config import settings
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    CouldNotRetrieveTranscript,
)

from app.utils.text_splitter import TranscriptSnippet

logger = logging.getLogger("vidscholar")


class TranscriptUnavailableError(Exception):
    """Raised when a transcript cannot be retrieved for any reason
    (disabled by uploader, no captions in a usable language, video
    unavailable/private, etc). The message is safe to show to end users."""
    pass


class TranscriptService:
    """Fetches and normalizes transcripts for a given YouTube video ID."""

    # Preferred language order: try English variants first, then fall back
    # to whatever auto-generated or translated track is available.
    DEFAULT_LANGUAGES = ("en", "en-US", "en-GB")

    def __init__(self) -> None:
        self._api = YouTubeTranscriptApi()

    def fetch_transcript(self, video_id: str) -> List[TranscriptSnippet]:
        """
        Returns the video's transcript as a list of TranscriptSnippet
        objects (text, start, duration), in chronological order.

        Raises:
            TranscriptUnavailableError: if no transcript could be retrieved
            in any supported language, or the video has captions disabled.
        """
        try:
            fetched = self._api.fetch(video_id, languages=list(self.DEFAULT_LANGUAGES))
        except NoTranscriptFound:
            # No transcript in our preferred languages — try to fall back
            # to ANY available transcript (e.g. auto-generated in another
            # language), which is still useful for embedding/search even
            # if not in English.
            logger.info(
                f"No transcript in {self.DEFAULT_LANGUAGES} for '{video_id}', "
                "attempting fallback to any available language."
            )
            fetched = self._fetch_any_available_transcript(video_id)
        except TranscriptsDisabled as exc:
            raise TranscriptUnavailableError(
                "The uploader has disabled transcripts/captions for this video."
            ) from exc
        except VideoUnavailable as exc:
            raise TranscriptUnavailableError(
                "This video is unavailable (it may be private, deleted, or region-locked)."
            ) from exc
        except CouldNotRetrieveTranscript:
            logger.warning(
            f"YouTube blocked transcript for '{video_id}'. "
            "Trying Supadata fallback."
            )

            return self._fetch_from_supadata(video_id)

        snippets = [
            TranscriptSnippet(text=s.text, start=s.start, duration=s.duration)
            for s in fetched
        ]

        if not snippets:
            raise TranscriptUnavailableError(
                "The transcript for this video was empty."
            )

        logger.info(f"Fetched {len(snippets)} transcript snippets for video '{video_id}'.")
        return snippets

    def _fetch_any_available_transcript(self, video_id: str):
        """
        Fallback path: lists every transcript track YouTube offers for
        this video (manually created or auto-generated, in any language)
        and fetches the first one found.
        """
        try:
            transcript_list = self._api.list(video_id)
        except Exception as exc:
            raise TranscriptUnavailableError(
                "No transcript is available for this video in any language."
            ) from exc

        for transcript in transcript_list:
            try:
                return transcript.fetch()
            except Exception as exc:  # noqa: BLE001 - try the next available track
                logger.warning(
                    f"Failed fetching fallback transcript track for '{video_id}': {exc}"
                )
                continue

        raise TranscriptUnavailableError(
            "No transcript is available for this video in any language."
        )
    
    def _fetch_from_supadata(self, video_id: str):
        response = requests.get(
            "https://api.supadata.ai/v1/youtube/transcript",
            headers={
                "x-api-key": settings.SUPADATA_API_KEY
            },
            params={
                "videoId": video_id
            },
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()
        logger.info(f"SUPADATA RESPONSE: {data}")
        snippets = []

        for item in data["transcript"]:
            snippets.append(
                TranscriptSnippet(
                    text=item["text"],
                    start=float(item["start"]),
                    duration=float(item["duration"]),
                )
            )

        logger.info(
            f"Fetched {len(snippets)} transcript snippets from Supadata for '{video_id}'."
        )

        return snippets