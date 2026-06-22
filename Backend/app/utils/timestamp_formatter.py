"""
VidScholar Backend - Timestamp Formatting Utilities
================================================
Converts raw second offsets (as returned by youtube-transcript-api) into
human-readable timestamps (e.g. "1:02:35" or "4:18") and into YouTube
deep-link URLs that jump straight to that moment in the video.

Used by:
  - vectorstore_service.py (when storing chunk metadata)
  - chat_service.py (when building citation objects for the frontend)
"""

from app.utils.youtube_utils import build_watch_url


def format_seconds_to_timestamp(total_seconds: float) -> str:
    """
    Converts a float number of seconds into a "H:MM:SS" or "M:SS" string.

    Examples:
        65.0    -> "1:05"
        3725.4  -> "1:02:05"
        0.0     -> "0:00"
    """
    if total_seconds is None or total_seconds < 0:
        total_seconds = 0

    whole_seconds = int(round(total_seconds))
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def build_timestamped_url(video_id: str, start_seconds: float) -> str:
    """
    Builds a YouTube URL that, when opened, seeks directly to `start_seconds`.
    Example: https://www.youtube.com/watch?v=VIDEO_ID&t=125s
    """
    base_url = build_watch_url(video_id)
    seconds_int = int(round(start_seconds)) if start_seconds else 0
    return f"{base_url}&t={seconds_int}s"
