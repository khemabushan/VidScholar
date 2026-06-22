// ============================================================
// VidScholar Frontend - Video Store (Global State)
// ============================================================
// A lightweight global store for the "currently active" video using
// React Context + useState, avoiding an extra state-management
// dependency (Zustand/Redux) for what is, at this stage, a single
// piece of shared state. If state needs grow significantly in later
// phases (chat history, generated content cache, etc.), this is the
// natural place to introduce useReducer or a dedicated library.

import { createContext, useContext, useState, type ReactNode } from "react";
import type { VideoResponse } from "@/types";

interface VideoStoreState {
  /** The video currently loaded in the workspace, or null if none yet. */
  currentVideo: VideoResponse | null;
  /** Replaces the current video (e.g. after processing completes). */
  setCurrentVideo: (video: VideoResponse | null) => void;
  /** Clears the current video, returning the UI to the empty/input state. */
  clearCurrentVideo: () => void;
}

const VideoStoreContext = createContext<VideoStoreState | undefined>(undefined);

export function VideoStoreProvider({ children }: { children: ReactNode }) {
  const [currentVideo, setCurrentVideo] = useState<VideoResponse | null>(null);

  const clearCurrentVideo = () => setCurrentVideo(null);

  return (
    <VideoStoreContext.Provider value={{ currentVideo, setCurrentVideo, clearCurrentVideo }}>
      {children}
    </VideoStoreContext.Provider>
  );
}

/**
 * Hook to access and update the currently active video from anywhere
 * in the component tree. Must be used within a <VideoStoreProvider>.
 */
export function useVideoStore(): VideoStoreState {
  const context = useContext(VideoStoreContext);
  if (context === undefined) {
    throw new Error("useVideoStore must be used within a VideoStoreProvider.");
  }
  return context;
}
