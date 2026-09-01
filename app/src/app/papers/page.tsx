"use client";

/**
 * My Papers: the research library.
 *
 * Search, filter, sort and delete all run against the backend rather than over
 * a client-side copy, so the list stays correct however large it grows and the
 * total is honest on every page.
 */

import { useCallback, useState } from "react";

import {
  EmptyLibrary,
  LibraryError,
  LibraryToolbar,
  LibraryUnavailable,
  LoadingRows,
  PaperCard,
} from "@/components/LibraryUI";
import { ApiError, deletePaper, type PaperListItem } from "@/lib/api";
import {
  DEFAULT_QUERY,
  useLibrary,
  useSelection,
  type LibraryQuery,
} from "@/lib/library";

export default function PapersPage() {
  const [query, setQuery] = useState<LibraryQuery>(DEFAULT_QUERY);
  const { state, reload } = useLibrary(query);
  const { isSelected, toggle } = useSelection();

  const [deleting, setDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const remove = useCallback(
    async (paper: PaperListItem) => {
      // Guarding on state as well as disabling the button: a fast second click
      // would otherwise fire a second DELETE for a row that is already gone.
      if (deleting) return;
      setDeleting(paper.id);
      setDeleteError(null);
      try {
        await deletePaper(paper.id);
        await reload();
      } catch (error) {
        setDeleteError(
          error instanceof ApiError
            ? error.message
            : "That paper could not be deleted. Please try again.",
        );
      } finally {
        setDeleting(null);
      }
    },
    [deleting, reload],
  );

  const filtered = Boolean(query.search) || query.status !== "all";

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">My Papers</h1>
          <p className="pagehead__sub">
            Papers you have saved, with their summary, research gaps and
            literature review. Select two or more to build a cross-paper review.
          </p>
        </div>
      </header>

      {state.kind === "unavailable" ? (
        <LibraryUnavailable detail={state.detail} />
      ) : state.kind === "failed" ? (
        <LibraryError message={state.error.message} onRetry={() => void reload()} />
      ) : (
        <>
          <LibraryToolbar
            query={query}
            onChange={setQuery}
            total={state.kind === "ready" ? state.data.total : undefined}
          />

          {deleteError && (
            <div className="notice notice--error" role="alert">
              <div>
                <p>{deleteError}</p>
              </div>
            </div>
          )}

          {state.kind === "loading" ? (
            <LoadingRows />
          ) : state.data.papers.length === 0 ? (
            <EmptyLibrary filtered={filtered} />
          ) : (
            <div className="paperlist">
              {state.data.papers.map((paper) => (
                <PaperCard
                  key={paper.id}
                  paper={paper}
                  selected={isSelected(paper.id)}
                  onToggle={toggle}
                  onDelete={remove}
                  deleting={deleting === paper.id}
                />
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
