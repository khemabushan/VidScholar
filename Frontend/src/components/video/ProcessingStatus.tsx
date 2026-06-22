// ============================================================
// VidScholar Frontend - Processing Status Indicator
// ============================================================
// Renders a visual indicator of where a video is in the processing
// pipeline (pending -> processing -> completed/failed), driven by the
// status value managed by useVideoProcessing.

import type { ProcessingStatus as Status } from "@/types";

interface ProcessingStatusProps {
  status: Status | "idle";
  errorMessage: string | null;
}

const STATUS_CONFIG: Record<
  Status | "idle",
  { label: string; dotClass: string; textClass: string; pulse: boolean }
> = {
  idle: { label: "Waiting for a URL", dotClass: "bg-slate-500", textClass: "text-slate-400", pulse: false },
  pending: { label: "Queued for processing", dotClass: "bg-amber-400", textClass: "text-amber-400", pulse: true },
  processing: {
    label: "Fetching transcript and building knowledge base...",
    dotClass: "bg-amber-400",
    textClass: "text-amber-400",
    pulse: true,
  },
  completed: { label: "Ready", dotClass: "bg-emerald-400", textClass: "text-emerald-400", pulse: false },
  failed: { label: "Processing failed", dotClass: "bg-red-400", textClass: "text-red-400", pulse: false },
};

export function ProcessingStatus({ status, errorMessage }: ProcessingStatusProps) {
  const config = STATUS_CONFIG[status];

  if (status === "idle") {
    return null;
  }

  return (
    <div className="w-full max-w-xl rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-center gap-2">
        <span
          className={`h-2.5 w-2.5 rounded-full ${config.dotClass} ${config.pulse ? "animate-pulse" : ""}`}
        />
        <span className={`text-sm font-medium ${config.textClass}`}>{config.label}</span>
      </div>
      {status === "failed" && errorMessage && (
        <p className="mt-2 text-sm text-slate-400 break-words">{errorMessage}</p>
      )}
    </div>
  );
}
