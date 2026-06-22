// ============================================================
// VidScholar Frontend - Shared TypeScript Types
// ============================================================
// These types mirror the Pydantic schemas defined in the backend at
// Backend/app/schemas/video.py. Keeping them in sync manually (rather
// than code-generating from the OpenAPI schema) is acceptable at this
// project's size, but if the backend schema changes, update here too.

/**
 * Mirrors the backend's ProcessingStatus enum exactly (app/schemas/video.py).
 */
export type ProcessingStatus = "pending" | "processing" | "completed" | "failed";

/**
 * Request body for POST /api/videos/process
 */
export interface VideoProcessRequest {
  url: string;
}

/**
 * Response returned immediately after POST /api/videos/process.
 */
export interface VideoProcessResponse {
  id: number;
  video_id: string;
  status: ProcessingStatus;
  message: string;
}

/**
 * Lightweight response from GET /api/videos/{id}/status, used for polling.
 */
export interface VideoStatusResponse {
  id: number;
  video_id: string;
  status: ProcessingStatus;
  error_message: string | null;
  chunk_count: number | null;
}

/**
 * Full video record returned from GET /api/videos/{id} and GET /api/videos.
 */
export interface VideoResponse {
  id: number;
  video_id: string;
  url: string;
  title: string | null;
  channel_name: string | null;
  thumbnail_url: string | null;
  duration_seconds: number | null;
  status: ProcessingStatus;
  error_message: string | null;
  chunk_count: number | null;
  created_at: string;
  updated_at: string;
}

// ------------------------------------------------------------------
// Chat With Video (mirrors Backend/app/schemas/chat.py)
// ------------------------------------------------------------------

/**
 * A single transcript chunk used to ground an answer, returned so the
 * UI can render a clickable timestamp badge under the assistant's reply.
 */
export interface Citation {
  chunk_index: number;
  text: string;
  start_time: number;
  end_time: number;
  timestamp_label: string;
  timestamped_url: string;
  relevance_score: number;
}

/** A single prior turn sent as conversational context on each new request. */
export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
}

/** Request body for POST /api/videos/{id}/chat and /chat/stream */
export interface ChatMessageRequest {
  message: string;
  top_k?: number;
  history?: ChatHistoryMessage[];
}

/** Full (non-streaming) response body for POST /api/videos/{id}/chat */
export interface ChatMessageResponse {
  answer: string;
  citations: Citation[];
  grounded: boolean;
}

/**
 * A single rendered turn in the chat transcript, used by the frontend
 * to track conversation state. Distinct from ChatHistoryMessage (which
 * is the wire format sent to the backend) because the UI needs extra
 * fields like citations, grounded, and a stable client-side id for
 * React keys.
 */
export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  grounded?: boolean;
  /** True while an assistant turn's answer is still streaming in. */
  isStreaming?: boolean;
  /** Set if this turn represents a request that failed outright (network/server error). */
  error?: string;
}

/** Parsed shape of each Server-Sent Event line from /chat/stream. */
export type ChatStreamEvent =
  | { type: "token"; content: string }
  | { type: "done"; citations: Citation[]; grounded: boolean }
  | { type: "error"; detail: string };
