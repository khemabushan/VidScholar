// ============================================================
// VidScholar Frontend - Chat Window
// ============================================================
// The main "Chat With Video" panel: a scrolling message list plus an
// input box. Delegates all state management to useChat and focuses
// purely on rendering + user input handling.

import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { useChat } from "@/hooks/useChat";
import { ChatBubble } from "@/components/chat/ChatBubble";

interface ChatWindowProps {
  videoRowId: number;
  videoId: string;
  videoTitle: string | null;
}

export function ChatWindow({
  videoRowId,
  videoId,
  videoTitle,
}: ChatWindowProps) {
  const { turns, isStreaming, sendMessage, clearChat } = useChat(videoRowId);
  const [draft, setDraft] = useState("");
  const [notes, setNotes] = useState("");
  const [loadingNotes, setLoadingNotes] = useState(false);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the latest message whenever the conversation grows
  // or the streaming answer's content updates.
  useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed || isStreaming) return;
    setDraft("");
    void sendMessage(trimmed);
  }
  async function generateNotes() {
  try {
    setLoadingNotes(true);
    console.log("videoRowId =", videoRowId);
    const response = await fetch(`http://127.0.0.1:8000/notes/${videoId}`);

    const data = await response.json();

    setNotes(data.notes);
  } catch (error) {
    console.error(error);
  } finally {
    setLoadingNotes(false);
  }
}

  return (
    <div className="flex w-full max-w-2xl flex-col rounded-lg border border-slate-800 bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">Chat with this video</h3>
          {videoTitle && <p className="text-xs text-slate-500 line-clamp-1">{videoTitle}</p>}
        </div>
        <div className="flex gap-2">
  <button
    onClick={generateNotes}
    className="rounded bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-500"
  >
    {loadingNotes ? "Generating..." : "Generate Notes"}
  </button>

  {turns.length > 0 && (
    <button
      onClick={clearChat}
      className="text-xs text-slate-500 underline hover:text-slate-300"
    >
      Clear chat
    </button>
  )}
</div>
      </div>

      <div className="flex h-96 flex-col gap-3 overflow-y-auto px-4 py-4">
        {turns.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-1 text-center text-sm text-slate-500">
            <p>Ask a question about this video.</p>
            <p className="text-xs text-slate-600">
              Answers are grounded in the video's transcript only.
            </p>
          </div>
        )}

        {turns.map((turn) => (
          <ChatBubble key={turn.id} turn={turn} />
        ))}
        <div ref={scrollAnchorRef} />
      </div>

{notes && (
  <div className="max-h-96 overflow-y-auto border-t border-slate-800 p-4">
    <h3 className="mb-3 text-lg font-bold text-green-400">
      Study Notes
    </h3>

    <div className="prose prose-invert max-w-none">
      <ReactMarkdown>
        {notes}
      </ReactMarkdown>
    </div>
  </div>
)}
      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-slate-800 p-3">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask something about this video..."
          disabled={isStreaming}
          className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isStreaming || !draft.trim()}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50 disabled:hover:bg-indigo-600"
        >
          {isStreaming ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}
