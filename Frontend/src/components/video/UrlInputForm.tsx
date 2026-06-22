// ============================================================
// VidScholar Frontend - URL Input Form
// ============================================================
// The primary entry point of the app: a text input + submit button
// for pasting a YouTube URL. Delegates all submission/polling logic
// to the useVideoProcessing hook and simply renders its current state.

import { useState, type FormEvent } from "react";

interface UrlInputFormProps {
  onSubmit: (url: string) => void;
  isSubmitting: boolean;
}

export function UrlInputForm({ onSubmit, isSubmitting }: UrlInputFormProps) {
  const [url, setUrl] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setLocalError("Please paste a YouTube URL or video ID.");
      return;
    }

    setLocalError(null);
    onSubmit(trimmedUrl);
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-xl">
      <label htmlFor="youtube-url" className="block text-sm font-medium text-slate-300 mb-2">
        YouTube URL
      </label>
      <div className="flex gap-2">
        <input
          id="youtube-url"
          type="text"
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            if (localError) setLocalError(null);
          }}
          placeholder="https://www.youtube.com/watch?v=..."
          disabled={isSubmitting}
          className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-4 py-2.5 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-indigo-600 px-5 py-2.5 font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-indigo-600"
        >
          {isSubmitting ? "Processing..." : "Analyze"}
        </button>
      </div>
      {localError && (
        <p className="mt-2 text-sm text-red-400" role="alert">
          {localError}
        </p>
      )}
      <p className="mt-2 text-xs text-slate-500">
        Supports full URLs, youtu.be links, shorts, and bare video IDs.
      </p>
    </form>
  );
}
