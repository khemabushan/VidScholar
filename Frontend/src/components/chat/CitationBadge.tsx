// ============================================================
// VidScholar Frontend - Citation Badge
// ============================================================
// Renders a small clickable badge for a single transcript citation
// (e.g. "0:42"). Clicking opens the source moment in a new tab via the
// timestamped YouTube URL. A future enhancement could instead seek the
// embedded <VideoPlayer> in-place rather than opening a new tab — left
// as a follow-up since that requires the YouTube IFrame Player API.

import type { Citation } from "@/types";

interface CitationBadgeProps {
  citation: Citation;
}

export function CitationBadge({ citation }: CitationBadgeProps) {
  return (
    <a
      href={citation.timestamped_url}
      target="_blank"
      rel="noopener noreferrer"
      title={citation.text}
      className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-xs font-medium text-indigo-300 transition-colors hover:border-indigo-500 hover:text-indigo-200"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="h-3 w-3"
      >
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
          clipRule="evenodd"
        />
      </svg>
      {citation.timestamp_label}
    </a>
  );
}

interface CitationListProps {
  citations: Citation[];
}

/** Renders a row of CitationBadge components, de-duplicated by chunk_index. */
export function CitationList({ citations }: CitationListProps) {
  if (citations.length === 0) return null;

  const seen = new Set<number>();
  const unique = citations.filter((c) => {
    if (seen.has(c.chunk_index)) return false;
    seen.add(c.chunk_index);
    return true;
  });

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-slate-500">Sources:</span>
      {unique.map((citation) => (
        <CitationBadge key={citation.chunk_index} citation={citation} />
      ))}
    </div>
  );
}
