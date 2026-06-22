// ============================================================
// VidScholar Frontend - Video Player
// ============================================================
// Embeds the processed YouTube video (via the standard iframe embed
// URL) alongside its title/channel metadata fetched from our backend.
// Later phases (Chat With Video) will extend this component with an
// imperative seek-to-timestamp capability for citation clicking.

import type { VideoResponse } from "@/types";

interface VideoPlayerProps {
  video: VideoResponse;
}

export function VideoPlayer({ video }: VideoPlayerProps) {
  const embedUrl = `https://www.youtube.com/embed/${video.video_id}`;

  return (
    <div className="w-full max-w-2xl">
      <div className="aspect-video w-full overflow-hidden rounded-lg border border-slate-800 bg-black">
        <iframe
          src={embedUrl}
          title={video.title ?? "YouTube video player"}
          allow="accelerate-toggle; encrypted-media; picture-in-picture"
          allowFullScreen
          className="h-full w-full"
        />
      </div>
      <div className="mt-3 space-y-1">
        <h2 className="text-lg font-semibold text-slate-100">
          {video.title ?? "Untitled video"}
        </h2>
        <div className="flex items-center gap-3 text-sm text-slate-400">
          {video.channel_name && <span>{video.channel_name}</span>}
          {video.duration_seconds != null && (
            <span>{formatDuration(video.duration_seconds)}</span>
          )}
          {video.chunk_count != null && (
            <span>{video.chunk_count} transcript chunks indexed</span>
          )}
        </div>
      </div>
    </div>
  );
}

/** Formats a duration in seconds as "H:MM:SS" or "M:SS" for display. */
function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  }
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
