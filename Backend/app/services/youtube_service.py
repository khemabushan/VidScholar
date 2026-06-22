"""
VidScholar Backend - YouTube Service
================================================
Responsible for fetching descriptive metadata about a YouTube video
(title, channel name, duration, thumbnail). Uses pytubefix under the
hood, which scrapes YouTube's player response since there's no official
free metadata API.

IMPORTANT: metadata fetching is treated as best-effort. If YouTube
changes its page structure, rate-limits us, or the network is
unavailable, we log the failure and return a partial/empty result
rather than raising — the rest of the pipeline (transcript extraction,
embedding, etc.) does not depend on this metadata and should not be
blocked by it.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from pytubefix import YouTube
from pytubefix.exceptions import PytubeFixError

from app.utils.youtube_utils import build_watch_url, build_thumbnail_url

logger = logging.getLogger("vidscholar")


@dataclass
class VideoMetadata:
    """Plain container for the metadata we care about, decoupled from
    pytubefix's YouTube object so callers don't need that import."""
    title: Optional[str] = None
    channel_name: Optional[str] = None
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None


class YouTubeService:
    """Fetches video metadata for a given video ID."""

    def fetch_metadata(self, video_id: str) -> VideoMetadata:
        """
        Attempts to retrieve title/channel/duration/thumbnail for a video.
        Always returns a VideoMetadata object — on any failure, returns
        one with as many fields populated as possible (at minimum, the
        thumbnail_url, which we can always construct without a network call).
        """
        # This fallback thumbnail works even if everything else fails,
        # since it's a deterministic URL pattern, not a scraped value.
        fallback_thumbnail = build_thumbnail_url(video_id)

        try:
            watch_url = build_watch_url(video_id)
            yt = YouTube(watch_url)

            return VideoMetadata(
                title=yt.title,
                channel_name=yt.author,
                duration_seconds=int(yt.length) if yt.length else None,
                thumbnail_url=yt.thumbnail_url or fallback_thumbnail,
            )
        except PytubeFixError as exc:
            logger.warning(
                f"pytubefix could not fetch metadata for video '{video_id}': {exc}. "
                "Continuing with partial metadata."
            )
        except Exception as exc:  # noqa: BLE001 - intentionally broad: metadata is non-critical
            logger.warning(
                f"Unexpected error fetching metadata for video '{video_id}': {exc}. "
                "Continuing with partial metadata."
            )

        return VideoMetadata(thumbnail_url=fallback_thumbnail)
