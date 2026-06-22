// ============================================================
// VidScholar Frontend - useVideoProcessing Hook
// ============================================================
// Encapsulates the full lifecycle of submitting a YouTube URL and
// polling its processing status until it reaches a terminal state
// (completed or failed). UI components (UrlInputForm, ProcessingStatus)
// consume this hook rather than calling the API functions directly,
// keeping polling/timing logic out of presentational components.

import { useCallback, useEffect, useRef, useState } from "react";
import { processVideo, getVideo } from "@/lib/api";
import type { ProcessingStatus, VideoResponse } from "@/types";

interface UseVideoProcessingResult {
  /** Current lifecycle status, or "idle" before any submission. */
  status: ProcessingStatus | "idle";
  /** The fully-loaded video record once status === "completed". */
  video: VideoResponse | null;
  /** Human-readable error message, set when status === "failed" or a network error occurs. */
  errorMessage: string | null;
  /** Submits a URL for processing and begins polling automatically. */
  submitUrl: (url: string) => Promise<void>;
  /** Resets all state back to "idle", e.g. when the user wants to try a different video. */
  reset: () => void;
}

const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 150; // 150 * 2s = 5 minutes ceiling, covers very long videos

/**
 * Manages submitting a YouTube URL and polling its processing status
 * until completion, exposing simple state for the UI to render.
 */
export function useVideoProcessing(): UseVideoProcessingResult {
  const [status, setStatus] = useState<ProcessingStatus | "idle">("idle");
  const [video, setVideo] = useState<VideoResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Tracks the active polling timer so it can be cleared on unmount or reset.
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guards against state updates after the component using this hook unmounts.
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
      }
    };
  }, []);

  const reset = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    setStatus("idle");
    setVideo(null);
    setErrorMessage(null);
  }, []);

  const pollStatus = useCallback((videoRowId: number, attempt: number) => {
    if (!isMountedRef.current) return;

    if (attempt >= MAX_POLL_ATTEMPTS) {
      setStatus("failed");
      setErrorMessage(
        "Processing is taking longer than expected. Please try again later."
      );
      return;
    }

    pollTimeoutRef.current = setTimeout(async () => {
      if (!isMountedRef.current) return;

      try {
        // Fetch the full record (not just /status) so that once we reach
        // "completed" we already have title/thumbnail/etc. ready to render
        // without a second round-trip.
        const fullVideo = await getVideo(videoRowId);
        if (!isMountedRef.current) return;

        setStatus(fullVideo.status);

        if (fullVideo.status === "completed") {
          setVideo(fullVideo);
        } else if (fullVideo.status === "failed") {
          setErrorMessage(fullVideo.error_message ?? "Processing failed for an unknown reason.");
        } else {
          // Still pending/processing — schedule the next poll.
          pollStatus(videoRowId, attempt + 1);
        }
      } catch (err) {
        if (!isMountedRef.current) return;
        setStatus("failed");
        setErrorMessage(err instanceof Error ? err.message : "Failed to check processing status.");
      }
    }, POLL_INTERVAL_MS);
  }, []);

  const submitUrl = useCallback(
    async (url: string) => {
      setStatus("processing");
      setVideo(null);
      setErrorMessage(null);

      try {
        const response = await processVideo(url);
        if (!isMountedRef.current) return;

        setStatus(response.status);

        if (response.status === "completed") {
          // Rare but possible if the backend treats this as an
          // already-processed video and short-circuits immediately.
          const fullVideo = await getVideo(response.id);
          if (isMountedRef.current) {
            setVideo(fullVideo);
          }
        } else {
          pollStatus(response.id, 0);
        }
      } catch (err) {
        if (!isMountedRef.current) return;
        setStatus("failed");
        setErrorMessage(err instanceof Error ? err.message : "Failed to submit video for processing.");
      }
    },
    [pollStatus]
  );

  return { status, video, errorMessage, submitUrl, reset };
}
