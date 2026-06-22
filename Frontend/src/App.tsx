// ============================================================
// VidScholar Frontend - Root App Component
// ============================================================
// Phase 1 scope: verify frontend <-> backend connectivity via /health.
// Phase 2 scope: full URL-submission -> processing -> video-display flow,
// using useVideoProcessing for the submit/poll lifecycle and VideoStoreProvider
// for sharing the active video with descendants in later phases (chat, notes, etc).

import { useEffect, useState } from "react";
import { checkBackendHealth, type HealthCheckResponse } from "@/lib/api";
import { useVideoProcessing } from "@/hooks/useVideoProcessing";
import { VideoStoreProvider, useVideoStore } from "@/store/videoStore";
import { UrlInputForm } from "@/components/video/UrlInputForm";
import { ProcessingStatus } from "@/components/video/ProcessingStatus";
import { VideoPlayer } from "@/components/video/VideoPlayer";
import { ChatWindow } from "@/components/chat/ChatWindow";

type ConnectionStatus = "checking" | "connected" | "error";

function BackendConnectionBanner() {
  const [status, setStatus] = useState<ConnectionStatus>("checking");
  const [healthData, setHealthData] = useState<HealthCheckResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let isMounted = true;

    async function verifyBackendConnection() {
      try {
        const data = await checkBackendHealth();
        if (isMounted) {
          setHealthData(data);
          setStatus("connected");
        }
      } catch (err) {
        if (isMounted) {
          setStatus("error");
          setErrorMessage(
            err instanceof Error ? err.message : "Unknown error contacting backend."
          );
        }
      }
    }

    verifyBackendConnection();
    return () => {
      isMounted = false;
    };
  }, []);

  if (status === "connected") {
    return (
      <div className="flex items-center justify-center gap-2 text-xs text-emerald-400">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        <span>
          Connected to {healthData?.service} v{healthData?.version}
        </span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center gap-1 text-xs text-red-400">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
          <span>Backend connection failed</span>
        </div>
        <span className="text-slate-600">{errorMessage}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center gap-2 text-xs text-amber-400">
      <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
      <span>Checking backend connection...</span>
    </div>
  );
}

function VideoWorkspace() {
  const { status, video, errorMessage, submitUrl, reset } = useVideoProcessing();
  const { setCurrentVideo } = useVideoStore();

  // Whenever processing completes, push the result into the shared
  // video store so other parts of the app (added in later phases,
  // e.g. chat, notes, flashcards) can read the active video.
  useEffect(() => {
    if (status === "completed" && video) {
  console.log(video);
  setCurrentVideo(video);
}
  }, [status, video, setCurrentVideo]);

  const isSubmitting = status === "pending" || status === "processing";

  return (
    <div className="flex w-full flex-col items-center gap-6">
      {!video && (
        <UrlInputForm onSubmit={submitUrl} isSubmitting={isSubmitting} />
      )}

      <ProcessingStatus status={status} errorMessage={errorMessage} />

      {video && (
        <div className="flex w-full flex-col items-center gap-4">
          <VideoPlayer video={video} />
          <ChatWindow
  videoRowId={video.id}
  videoId={video.video_id}
  videoTitle={video.title}
/>
          <button
            onClick={() => {
              reset();
              setCurrentVideo(null);
            }}
            className="text-sm text-slate-400 underline hover:text-slate-200"
          >
            Analyze a different video
          </button>
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <VideoStoreProvider>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <header className="border-b border-slate-900 px-4 py-4">
          <div className="mx-auto flex max-w-4xl flex-col items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">VidScholar</h1>
            <p className="text-sm text-slate-400">
              AI Powered YouTube Learning Assistant
            </p>
            <BackendConnectionBanner />
          </div>
        </header>

        <main className="mx-auto flex max-w-4xl flex-col items-center gap-8 px-4 py-12">
          <VideoWorkspace />
        </main>
      </div>
    </VideoStoreProvider>
  );
}

export default App;