// ============================================================
// VidScholar Frontend - useChat Hook
// ============================================================
// Manages the full chat conversation state for a single video: sending
// messages, streaming the assistant's reply token-by-token, tracking
// citations, and surfacing errors. Components (ChatWindow) consume this
// hook rather than calling the API layer directly.

import { useCallback, useRef, useState } from "react";
import { sendChatMessageStream } from "@/lib/api";
import type { ChatHistoryMessage, ChatTurn } from "@/types";

interface UseChatResult {
  turns: ChatTurn[];
  isStreaming: boolean;
  sendMessage: (message: string) => Promise<void>;
  clearChat: () => void;
}

/** Generates a reasonably unique id for React keys without adding a uuid dependency. */
function generateTurnId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Manages a chat conversation against a specific video's transcript,
 * including streaming the assistant's response token-by-token and
 * tracking which transcript citations grounded each answer.
 */
export function useChat(videoRowId: number | null): UseChatResult {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // Tracks the in-flight request so a new message can cancel a
  // still-streaming previous one (e.g. if the user sends again quickly).
  const abortControllerRef = useRef<AbortController | null>(null);

  const clearChat = useCallback(() => {
    abortControllerRef.current?.abort();
    setTurns([]);
    setIsStreaming(false);
  }, []);

  const sendMessage = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || videoRowId === null) return;

      // Cancel any still-in-flight stream before starting a new one.
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const userTurn: ChatTurn = {
        id: generateTurnId(),
        role: "user",
        content: trimmed,
      };
      const assistantTurnId = generateTurnId();
      const assistantTurn: ChatTurn = {
        id: assistantTurnId,
        role: "assistant",
        content: "",
        isStreaming: true,
      };

      // Build the history payload from turns BEFORE this exchange, so the
      // backend has conversational context without us re-sending the
      // brand-new user/assistant turns we're about to append.
      const history: ChatHistoryMessage[] = turns
        .filter((t) => !t.error)
        .map((t) => ({ role: t.role, content: t.content }));

      setTurns((prev) => [...prev, userTurn, assistantTurn]);
      setIsStreaming(true);

      function updateAssistantTurn(updates: Partial<ChatTurn>) {
        setTurns((prev) =>
          prev.map((t) => (t.id === assistantTurnId ? { ...t, ...updates } : t))
        );
      }

      try {
        await sendChatMessageStream(
          videoRowId,
          trimmed,
          (event) => {
            if (event.type === "token") {
              setTurns((prev) =>
                prev.map((t) =>
                  t.id === assistantTurnId ? { ...t, content: t.content + event.content } : t
                )
              );
            } else if (event.type === "done") {
              updateAssistantTurn({
                citations: event.citations,
                grounded: event.grounded,
                isStreaming: false,
              });
            } else if (event.type === "error") {
              updateAssistantTurn({ error: event.detail, isStreaming: false });
            }
          },
          { history, signal: controller.signal }
        );
      } catch (err) {
        // AbortError fires when a newer message superseded this one —
        // that's expected and not a real error worth showing the user.
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        updateAssistantTurn({
          error: err instanceof Error ? err.message : "Failed to get a response.",
          isStreaming: false,
        });
      } finally {
        if (abortControllerRef.current === controller) {
          setIsStreaming(false);
        }
      }
    },
    [videoRowId, turns]
  );

  return { turns, isStreaming, sendMessage, clearChat };
}
