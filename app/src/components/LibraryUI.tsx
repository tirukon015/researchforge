"use client";

/**
 * Shared pieces of the research library: the not-connected notice, the search
 * and filter toolbar, and the paper card.
 *
 * They live together because all three appear on My Papers and on Workspace,
 * and duplicating them would let the two pages drift into describing the same
 * library differently.
 */

import Link from "next/link";

import EmptyState from "@/components/EmptyState";
import {
  IconAlert,
  IconCheck,
  IconFile,
  IconInfo,
  IconSearch,
  IconTrash,
} from "@/components/Icons";
import type { PaperListItem, PaperStatus, SortOrder } from "@/lib/api";
import { formatDate, formatSize, type LibraryQuery } from "@/lib/library";

/* ------------------------------------------------------------------ *
 * States
 * ------------------------------------------------------------------ */

/**
 * Shown when no database is configured.
 *
 * This is deliberately NOT an empty library. "You have no papers" is a claim,
 * and a deployment with nowhere to store papers is not in a position to make
 * it. The wording says the library is not connected and that analysis still
 * works, which is the part the reader can act on.
 */
export function LibraryUnavailable({ detail }: { detail?: string }) {
  return (
    <div className="card">
      <EmptyState
        art
        title="The research library is not connected"
        actions={
          <Link href="/dashboard" className="btn btn--primary">
            Analyse a paper
          </Link>
        }
      >
        {detail ||
          "Saving papers needs durable storage, which this deployment does not have yet."}{" "}
        Analysis works normally, and results stay available for the rest of your
        visit.
      </EmptyState>
    </div>
  );
}

export function LibraryError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="card">
      <EmptyState icon={<IconAlert size={28} />} title="Could not load your library">
        <p style={{ margin: 0 }}>{message}</p>
        <div className="empty__actions">
          <button className="btn btn--primary" onClick={onRetry}>
            Try again
          </button>
        </div>
      </EmptyState>
    </div>
  );
}

/** A neutral placeholder while a remote read is in flight. */
export function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading your papers</span>
      {Array.from({ length: rows }).map((_, i) => (
        <div className="skeleton" key={i}>
          <div className="skeleton__line skeleton__line--title" />
          <div className="skeleton__line" />
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Toolbar
 * ------------------------------------------------------------------ */

const STATUSES: { value: PaperStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "ready", label: "Analysed" },
  { value: "processing", label: "Processing" },
  { value: "failed", label: "Failed" },
];

const SORTS: { value: SortOrder; label: string }[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "title", label: "Title" },
];

export function LibraryToolbar({
  query,
  onChange,
  total,
}: {
  query: LibraryQuery;
  onChange: (next: LibraryQuery) => void;
  total?: number;
}) {
  return (
    <div className="toolbar">
      <div className="toolbar__search">
        <IconSearch size={16} />
        <input
          type="search"
          value={query.search}
          onChange={(e) => onChange({ ...query, search: e.target.value })}
          placeholder="Search title or filename"
          aria-label="Search your papers by title or filename"
        />
      </div>

      <div className="toolbar__group">
        <label className="toolbar__label" htmlFor="filter-status">
          Show
        </label>
        <select
          id="filter-status"
          value={query.status}
          onChange={(e) =>
            onChange({ ...query, status: e.target.value as PaperStatus | "all" })
          }
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="toolbar__group">
        <label className="toolbar__label" htmlFor="sort-order">
          Sort
        </label>
        <select
          id="sort-order"
          value={query.sort}
          onChange={(e) => onChange({ ...query, sort: e.target.value as SortOrder })}
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {typeof total === "number" && (
        <span className="toolbar__count faint">
          {total} paper{total === 1 ? "" : "s"}
        </span>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Paper card
 * ------------------------------------------------------------------ */

const STATUS_BADGE: Record<PaperStatus, { label: string; className: string }> = {
  ready: { label: "Analysed", className: "badge badge--ok" },
  processing: { label: "Processing", className: "badge" },
  failed: { label: "Failed", className: "badge badge--err" },
};

export function PaperCard({
  paper,
  selected,
  onToggle,
  onDelete,
  deleting = false,
}: {
  paper: PaperListItem;
  selected?: boolean;
  onToggle?: (paper: PaperListItem) => void;
  onDelete?: (paper: PaperListItem) => void;
  deleting?: boolean;
}) {
  const badge = STATUS_BADGE[paper.status];

  return (
    <article className={`papercard${selected ? " papercard--selected" : ""}`}>
      {onToggle && (
        <label className="papercard__pick">
          <input
            type="checkbox"
            checked={Boolean(selected)}
            onChange={() => onToggle(paper)}
            aria-label={`Select ${paper.title} for a cross-paper review`}
          />
          <span aria-hidden="true">{selected ? <IconCheck size={14} /> : null}</span>
        </label>
      )}

      <IconFile size={22} className="papercard__icon" />

      <div className="papercard__body">
        <h3 className="papercard__title">
          <Link href={`/papers/${paper.id}`}>{paper.title}</Link>
        </h3>
        <p className="papercard__meta">
          {paper.filename}
          {paper.page_count != null && ` · ${paper.page_count} pages`}
          {` · ${formatSize(paper.file_size_bytes)} · ${formatDate(paper.created_at)}`}
        </p>
        <div className="tagrow">
          <span className={badge.className}>{badge.label}</span>
          {paper.gap_count != null && (
            <span className="badge">
              {paper.gap_count} gap{paper.gap_count === 1 ? "" : "s"}
            </span>
          )}
          {!paper.has_analysis && <span className="badge">No analysis stored</span>}
        </div>
      </div>

      <div className="papercard__actions">
        <Link href={`/papers/${paper.id}`} className="btn btn--sm">
          Open
        </Link>
        {onDelete && (
          <button
            className="btn btn--sm btn--danger"
            onClick={() => onDelete(paper)}
            disabled={deleting}
            aria-label={`Delete ${paper.title}`}
          >
            <IconTrash size={14} />
            {deleting ? "Deleting" : "Delete"}
          </button>
        )}
      </div>
    </article>
  );
}

/** Shown when the library is genuinely connected and genuinely empty. */
export function EmptyLibrary({ filtered }: { filtered: boolean }) {
  if (filtered) {
    return (
      <div className="card">
        <EmptyState icon={<IconSearch size={28} />} title="No papers match that search">
          Try a different term, or clear the filters to see everything in your
          library.
        </EmptyState>
      </div>
    );
  }
  return (
    <div className="card">
      <EmptyState
        art
        title="Your research library is empty"
        actions={
          <Link href="/dashboard" className="btn btn--primary">
            Upload your first paper
          </Link>
        }
      >
        Papers you save after analysing them will be listed here, with their
        summary, research gaps and literature review.
      </EmptyState>
    </div>
  );
}

/** A short, calm notice. Used for scope statements, never for errors. */
export function InfoNotice({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice notice--info">
      <IconInfo size={16} />
      <div>{children}</div>
    </div>
  );
}
