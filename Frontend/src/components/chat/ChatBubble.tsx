// ============================================================
// VidScholar Frontend - Chat Bubble
// ============================================================
// Renders a single turn in the conversation: a user question (right-
// aligned) or an assistant answer (left-aligned), including streaming
// cursor, citations, "not covered in this video" styling, and error state.

import type { ChatTurn } from "@/types";
import { CitationList } from "@/components/chat/CitationBadge";

interface ChatBubbleProps {
  turn: ChatTurn;
}

export function ChatBubble({ turn }: ChatBubbleProps) {
  const isUser = turn.role === "user";

  // An assistant turn that finished streaming but came back ungrounded
  // (the model found nothing relevant in the transcript) gets a visibly
  // different style from a normal grounded answer, so the person can
  // immediately tell the difference between "here's what the video
  // says" and "the video doesn't cover that."
  const isUngrounded = !isUser && turn.grounded === false && !turn.isStreaming;

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
          isUser
            ? "bg-indigo-600 text-white"
            : isUngrounded
              ? "border border-amber-800/50 bg-amber-950/30 text-amber-200"
              : "border border-slate-800 bg-slate-900 text-slate-100"
        }`}
      >
        {turn.error ? (
          <p className="text-red-400">{turn.error}</p>
        ) : (
          <>
            <p className="whitespace-pre-wrap break-words">
              {turn.content}
              {turn.isStreaming && (
                <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-slate-400 align-middle" />
              )}
            </p>
            {!isUser && turn.citations && turn.citations.length > 0 && (
              <CitationList citations={turn.citations} />
            )}
          </>
        )}
      </div>
    </div>
  );
}
