"use client";

/**
 * Research workspace: choose the papers a cross-paper review will be built
 * from.
 *
 * Selection and the browsable library sit on one screen because choosing is a
 * comparison task. Sending the user to a separate picker would mean holding
 * the shortlist in their head while they browse.
 *
 * The selected panel lists every chosen paper by name. That is what lets the
 * generated review claim "based on N papers" and have the claim be checkable.
 */

import Link from "next/link";
import { useState } from "react";

import EmptyState from "@/components/EmptyState";
import { IconClose, IconReview, IconStack } from "@/components/Icons";
import {
  EmptyLibrary,
  LibraryError,
  LibraryToolbar,
  LibraryUnavailable,
  LoadingRows,
  PaperCard,
} from "@/components/LibraryUI";
import {
  DEFAULT_QUERY,
  useLibrary,
  useSelection,
  type LibraryQuery,
} from "@/lib/library";

export default function WorkspacePage() {
  const [query, setQuery] = useState<LibraryQuery>(DEFAULT_QUERY);
  const { state, reload } = useLibrary(query);
  const { selected, isSelected, toggle, remove, clear, canReview } = useSelection();

  const filtered = Boolean(query.search) || query.status !== "all";

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">Research Workspace</h1>
          <p className="pagehead__sub">
            Browse your library, select the papers you want to compare, then
            generate one literature review across all of them.
          </p>
        </div>
      </header>

      <div className="workspace">
        <section className="workspace__main" aria-labelledby="browse-heading">
          <div className="section__head">
            <h2 className="section__title" id="browse-heading">
              Your papers
            </h2>
          </div>

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
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </section>

        <aside className="workspace__panel" aria-labelledby="selected-heading">
          <div className="card">
            <div className="card__head">
              <div>
                <h2 className="card__title" id="selected-heading">
                  Selected papers ({selected.length})
                </h2>
                <p className="card__hint">
                  A cross-paper review needs at least two.
                </p>
              </div>
              {selected.length > 0 && (
                <button className="btn btn--sm btn--ghost" onClick={clear}>
                  Clear
                </button>
              )}
            </div>

            <div className="card__body">
              {selected.length === 0 ? (
                <EmptyState icon={<IconStack size={26} />} title="Nothing selected yet">
                  Tick the papers you want to review together. They will be
                  listed here in the order you choose them.
                </EmptyState>
              ) : (
                <>
                  <ul className="selectedlist">
                    {selected.map((paper, i) => (
                      <li key={paper.id}>
                        <span className="selectedlist__n">{i + 1}</span>
                        <span className="selectedlist__title">
                          <Link href={`/papers/${paper.id}`}>{paper.title}</Link>
                        </span>
                        <button
                          className="iconbtn iconbtn--sm"
                          onClick={() => remove(paper.id)}
                          aria-label={`Remove ${paper.title} from the selection`}
                        >
                          <IconClose size={13} />
                        </button>
                      </li>
                    ))}
                  </ul>

                  <Link
                    href="/literature-review"
                    className={`btn btn--primary btn--lg${canReview ? "" : " btn--disabled"}`}
                    aria-disabled={!canReview}
                    // A disabled anchor is still focusable and still navigable,
                    // so the click is stopped explicitly rather than relying on
                    // styling alone.
                    onClick={(e) => {
                      if (!canReview) e.preventDefault();
                    }}
                    style={{ width: "100%", marginTop: "1rem" }}
                  >
                    <IconReview size={16} />
                    Generate literature review
                  </Link>
                  {!canReview && (
                    <p className="card__hint" style={{ marginTop: ".6rem" }}>
                      Select one more paper to continue. A review of a single
                      paper is already produced when you analyse it.
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}
