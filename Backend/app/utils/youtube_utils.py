"""
VidScholar Backend - YouTube URL Utilities
================================================
Pure utility functions for parsing YouTube URLs and extracting the
11-character video ID. Kept dependency-free (no network calls) so it
can be unit tested trivially and reused anywhere in the codebase.

Supports the common URL formats:
  - https://www.youtube.com/watch?v=VIDEO_ID
  - https://youtu.be/VIDEO_ID
  - https://www.youtube.com/embed/VIDEO_ID
  - https://www.youtube.com/shorts/VIDEO_ID
  - https://m.youtube.com/watch?v=VIDEO_ID
  - Raw 11-character video ID pasted directly
"""

import re
from urllib.parse import urlparse, parse_qs


class InvalidYouTubeURLError(ValueError):
    """Raised when a string cannot be parsed into a valid YouTube video ID."""
    pass


# A valid YouTube video ID is exactly 11 characters of base64url-safe charset.
_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    """
    Extracts the 11-character YouTube video ID from a full URL or returns
    the input unchanged if it already looks like a bare video ID.

    Raises:
        InvalidYouTubeURLError: if no valid video ID can be determined.
    """
    if not url_or_id or not isinstance(url_or_id, str):
        raise InvalidYouTubeURLError("URL must be a non-empty string.")

    candidate = url_or_id.strip()

    # Case 1: the user pasted a bare video ID (no scheme, no slashes).
    if _VIDEO_ID_PATTERN.match(candidate):
        return candidate

    # Case 2: a full URL. Ensure it has a scheme so urlparse behaves correctly.
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://" + candidate

    parsed = urlparse(candidate)
    hostname = (parsed.hostname or "").lower().replace("www.", "").replace("m.", "")

    if hostname not in {"youtube.com", "youtu.be", "youtube-nocookie.com"}:
        raise InvalidYouTubeURLError(
            f"'{url_or_id}' is not a recognized YouTube URL."
        )

    # youtu.be short links: https://youtu.be/VIDEO_ID
    if hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
        if _VIDEO_ID_PATTERN.match(video_id):
            return video_id
        raise InvalidYouTubeURLError(f"Could not extract a valid video ID from '{url_or_id}'.")

    # Standard watch URL: https://www.youtube.com/watch?v=VIDEO_ID
    if parsed.path == "/watch":
        query_params = parse_qs(parsed.query)
        video_ids = query_params.get("v")
        if video_ids and _VIDEO_ID_PATTERN.match(video_ids[0]):
            return video_ids[0]
        raise InvalidYouTubeURLError(f"No 'v' parameter found in URL '{url_or_id}'.")

    # Embed or shorts URLs: /embed/VIDEO_ID or /shorts/VIDEO_ID
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
        video_id = path_parts[1]
        if _VIDEO_ID_PATTERN.match(video_id):
            return video_id

    raise InvalidYouTubeURLError(
        f"Could not extract a valid video ID from '{url_or_id}'."
    )


def build_watch_url(video_id: str) -> str:
    """Builds a canonical watch URL from a video ID, used for display/links."""
    return f"https://www.youtube.com/watch?v={video_id}"


def build_thumbnail_url(video_id: str, quality: str = "hqdefault") -> str:
    """
    Builds a thumbnail URL for a video ID without needing any API call.
    Valid quality values: default, mqdefault, hqdefault, sddefault, maxresdefault.
    """
    return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
