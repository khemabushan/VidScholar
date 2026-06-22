// ============================================================
// VidScholar Frontend - API Client
// ============================================================
// Centralized Axios instance for all backend calls. Every feature
// module imports `apiClient` from here instead of creating its own
// axios instances, ensuring consistent base URL, timeouts, and error
// handling. Phase 2 adds the video-processing endpoints on top of the
// Phase 1 health check.

import axios, { type AxiosInstance, AxiosError } from "axios";
import type {
  VideoProcessRequest,
  VideoProcessResponse,
  VideoStatusResponse,
  VideoResponse,
  ChatMessageRequest,
  ChatMessageResponse,
  ChatStreamEvent,
  ChatHistoryMessage,
} from "@/types";

// Vite exposes env vars prefixed with VITE_ via import.meta.env.
// Falls back to localhost:8000 if not set, so the app still works
// out of the box without requiring a .env file in Phase 1.
const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000, // 15s — generous enough for cold starts, later raised per-endpoint for long LLM calls
  headers: {
    "Content-Type": "application/json",
  },
});

// ------------------------------------------------------------------
// Shared response/error types
// ------------------------------------------------------------------
export interface HealthCheckResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ApiErrorShape {
  success: false;
  error: string;
}

/**
 * FastAPI's default validation error shape (HTTP 422), returned when a
 * Pydantic field validator rejects the request body — e.g. submitting
 * a non-YouTube URL to POST /api/videos/process.
 */
interface ValidationErrorShape {
  detail: Array<{ msg: string; loc: (string | number)[] }> | string;
}

/**
 * Normalizes any error thrown by an API call into a readable message.
 * Used so UI components don't need to know about Axios internals.
 */
export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorShape | ValidationErrorShape>;
    const data = axiosError.response?.data;

    if (data && "error" in data && data.error) {
      return data.error;
    }

    if (data && "detail" in data && data.detail) {
      if (typeof data.detail === "string") {
        return data.detail;
      }
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        return data.detail.map((d) => d.msg).join(" ");
      }
    }

    if (axiosError.code === "ECONNABORTED") {
      return "Request timed out. Please try again.";
    }
    if (!axiosError.response) {
      return `Could not reach the backend at ${API_BASE_URL}. Is the server running?`;
    }
    return axiosError.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "An unknown error occurred.";
}

// ------------------------------------------------------------------
// Health check call
// ------------------------------------------------------------------
/**
 * Calls the backend's /health endpoint to verify connectivity.
 * Used by App.tsx on mount in Phase 1.
 */
export async function checkBackendHealth(): Promise<HealthCheckResponse> {
  try {
    const response = await apiClient.get<HealthCheckResponse>("/health");
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

// ------------------------------------------------------------------
// Video processing calls (Phase 2)
// ------------------------------------------------------------------

/**
 * Submits a YouTube URL for processing. The backend creates (or reuses)
 * a video record and kicks off background transcript extraction +
 * embedding. Returns immediately with a "processing" status — call
 * getVideoStatus() afterward to poll for completion.
 */
export async function processVideo(url: string): Promise<VideoProcessResponse> {
  try {
    const payload: VideoProcessRequest = { url };
    const response = await apiClient.post<VideoProcessResponse>(
      "/api/videos/process",
      payload
    );
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

/**
 * Polls the processing status of a video by its internal row ID
 * (the `id` field returned from processVideo, NOT the YouTube video_id).
 */
export async function getVideoStatus(videoRowId: number): Promise<VideoStatusResponse> {
  try {
    const response = await apiClient.get<VideoStatusResponse>(
      `/api/videos/${videoRowId}/status`
    );
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

/**
 * Fetches the full record (title, channel, thumbnail, status, etc.)
 * for a single processed video.
 */
export async function getVideo(videoRowId: number): Promise<VideoResponse> {
  try {
    const response = await apiClient.get<VideoResponse>(`/api/videos/${videoRowId}`);
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

/**
 * Fetches the most recently processed videos, most recent first.
 */
export async function listVideos(limit = 50, offset = 0): Promise<VideoResponse[]> {
  try {
    const response = await apiClient.get<VideoResponse[]>("/api/videos", {
      params: { limit, offset },
    });
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

/**
 * Deletes a video's database record and its associated vector store
 * collection on the backend.
 */
export async function deleteVideo(videoRowId: number): Promise<void> {
  try {
    await apiClient.delete(`/api/videos/${videoRowId}`);
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

// ------------------------------------------------------------------
// Chat With Video calls (Phase 4)
// ------------------------------------------------------------------

/**
 * Sends a chat message and waits for the full answer in one response.
 * Simpler than sendChatMessageStream but the UI won't see tokens arrive
 * progressively — prefer the streaming variant for the main chat UI and
 * keep this one for any non-interactive/background use cases.
 */
export async function sendChatMessage(
  videoRowId: number,
  message: string,
  options?: { topK?: number; history?: ChatHistoryMessage[] }
): Promise<ChatMessageResponse> {
  try {
    const payload: ChatMessageRequest = {
      message,
      top_k: options?.topK,
      history: options?.history,
    };
    // Chat answers can take longer than the default 15s timeout,
    // especially for longer transcripts/contexts, so this call uses an
    // extended timeout rather than the shared apiClient default.
    const response = await apiClient.post<ChatMessageResponse>(
      `/api/videos/${videoRowId}/chat`,
      payload,
      { timeout: 60000 }
    );
    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error));
  }
}

/**
 * Sends a chat message and streams the answer back token-by-token via
 * Server-Sent Events. Uses the native fetch API directly rather than
 * axios, because axios's browser adapter does not expose a readable
 * stream for the response body — fetch's `response.body` ReadableStream
 * is what lets us parse SSE events as they arrive instead of waiting
 * for the entire response to complete.
 *
 * `onEvent` is called once per parsed SSE event (token/done/error).
 * Throws if the initial connection itself fails (network error, 404,
 * 409, etc) — those are surfaced as a rejected promise rather than an
 * "error" stream event, since the stream never started in that case.
 */
export async function sendChatMessageStream(
  videoRowId: number,
  message: string,
  onEvent: (event: ChatStreamEvent) => void,
  options?: { topK?: number; history?: ChatHistoryMessage[]; signal?: AbortSignal }
): Promise<void> {
  const payload: ChatMessageRequest = {
    message,
    top_k: options?.topK,
    history: options?.history,
  };

  const response = await fetch(`${API_BASE_URL}/api/videos/${videoRowId}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options?.signal,
  });

  if (!response.ok) {
    // The backend returns a normal JSON error body (404/409/422/503)
    // when the request is rejected before streaming even starts.
    let detail = `Request failed with status ${response.status}.`;
    try {
      const errorBody = await response.json();
      detail = errorBody?.detail ?? detail;
    } catch {
      // response body wasn't JSON — fall back to the generic message above.
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (!response.body) {
    throw new Error("This browser does not support streaming responses.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line ("\n\n"). Split on that
    // boundary and process each complete event, keeping any trailing
    // partial event in the buffer for the next chunk.
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const line = rawEvent.trim();
      if (!line.startsWith("data:")) continue;

      const jsonStr = line.slice("data:".length).trim();
      if (!jsonStr) continue;

      try {
        const parsed = JSON.parse(jsonStr) as ChatStreamEvent;
        onEvent(parsed);
      } catch {
        // Malformed event line — skip it rather than crashing the whole stream.
        continue;
      }
    }
  }
}
