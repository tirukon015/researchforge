"use client";

/**
 * Literature Review: single paper and cross paper.
 *
 * The scope of each is stated above its content, not in a footnote. A page
 * titled "Literature Review" invites the reader to assume a corpus was
 * searched; the single-paper review reads one paper's own related work, and
 * the cross-paper review covers exactly the papers named on screen and nothing
 * else. Both say so.
 */

import Link from "next/link";
import { useCallback, useState } from "react";

import { ReviewSection } from "@/components/AnalysisSections";
import EmptyState from "@/components/EmptyState";
import { IconAlert, IconReview, IconSpark, IconStack } from "@/components/Icons";
import { InfoNotice } from "@/components/LibraryUI";
import { ApiError, createCrossReview, type ReviewRecord } from "@/lib/api";
import { useSelection } from "@/lib/library";
import { useSession } from "@/lib/session";

type GenState =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "done"; review: ReviewRecord }
  | { kind: "unavailable"; detail: string }
  // `exhausted` suppresses the retry button. Offering "Try again" against a
  // spent quota invites the user to burn what little allowance is left on a
  // request that cannot succeed.
  | { kind: "failed"; detail: string; exhausted?: boolean };

export default function LiteratureReviewPage() {
  const { current } = useSession();
  const { selected, canReview, clear } = useSelection();
  const [gen, setGen] = useState<GenState>({ kind: "idle" });

  const generate = useCallback(async () => {
    // Guard as well as disable: a cross-paper review is an expensive call and
    // a double submit would pay for it twice.
    if (gen.kind === "working" || !canReview) return;
    setGen({ kind: "working" });
    try {
      const review = await createCrossReview(selected.map((p) => p.id));
      setGen({ kind: "done", review });
    } catch (error) {
      if (error instanceof ApiError && error.kind === "unavailable") {
        setGen({ kind: "unavailable", detail: error.message });
        return;
      }
      setGen({
        kind: "failed",
        detail:
          error instanceof ApiError
            ? error.message
            : "The review could not be generated. Please try again.",
        exhausted:
          error instanceof ApiError &&
          error.kind === "ratelimited" &&
          error.quotaExhausted === true,
      });
    }
  }, [gen.kind, canReview, selected]);

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">Literature Review</h1>
          <p className="pagehead__sub">
            Review the prior work inside a single paper, or compare several
            saved papers in one review.
          </p>
        </div>
      </header>

      {/* ---------------- cross-paper ---------------- */}

      <section className="section" aria-labelledby="cross-heading">
        <div className="section__head">
          <h2 className="section__title" id="cross-heading">
            Cross-paper review
          </h2>
          <Link href="/workspace" className="btn btn--sm">
            Choose papers
          </Link>
        </div>

        {gen.kind === "done" ? (
          <div className="card">
            <div className="card__head">
              <div>
                <h3 className="card__title">{gen.review.title}</h3>
                <p className="card__hint">
                  Based on {gen.review.paper_count} selected paper
                  {gen.review.paper_count === 1 ? "" : "s"}.
                </p>
              </div>
              <button
                className="btn btn--sm"
                onClick={() => {
                  setGen({ kind: "idle" });
                  clear();
                }}
              >
                Start another
              </button>
            </div>
            <div className="card__body">
              {/* The papers are named, not merely counted, so the claim above
                  can be checked rather than trusted. */}
              <div className="block">
                <div className="block__head">
                  <h4>Papers included</h4>
                </div>
                <ul className="selectedlist selectedlist--static">
                  {gen.review.papers.map((p, i) => (
                    <li key={p.id}>
                      <span className="selectedlist__n">{i + 1}</span>
                      <span className="selectedlist__title">
                        <Link href={`/papers/${p.id}`}>{p.title}</Link>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="tabpanel">
              <ReviewSection review={gen.review.content} />
            </div>
          </div>
        ) : (
          <div className="card">
            <div className="card__body">
              {selected.length === 0 ? (
                <EmptyState
                  icon={<IconStack size={28} />}
                  title="No papers selected"
                  actions={
                    <Link href="/workspace" className="btn btn--primary">
                      Open the workspace
                    </Link>
                  }
                >
                  Analyse a paper, or select two or more saved papers in the
                  workspace, to build a literature review across them.
                </EmptyState>
              ) : (
                <>
                  <div className="block">
                    <div className="block__head">
                      <h4>
                        Selected papers{" "}
                        <span className="faint">({selected.length})</span>
                      </h4>
                    </div>
                    <ul className="selectedlist selectedlist--static">
                      {selected.map((p, i) => (
                        <li key={p.id}>
                          <span className="selectedlist__n">{i + 1}</span>
                          <span className="selectedlist__title">{p.title}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="btnrow">
                    <button
                      className="btn btn--primary btn--lg"
                      onClick={() => void generate()}
                      disabled={!canReview || gen.kind === "working"}
                    >
                      <IconSpark size={16} />
                      {gen.kind === "working"
                        ? "Generating review"
                        : `Generate review of ${selected.length} papers`}
                    </button>
                    <Link href="/workspace" className="btn">
                      Change selection
                    </Link>
                  </div>

                  {!canReview && (
                    <p className="card__hint" style={{ marginTop: ".7rem" }}>
                      Select at least two papers. A review of one paper is
                      already produced when you analyse it.
                    </p>
                  )}

                  {gen.kind === "working" && (
                    <div className="progress" role="status" aria-live="polite">
                      <div className="progress__bar">
                        <span />
                      </div>
                      <p className="card__hint" style={{ marginTop: ".7rem" }}>
                        Reading the stored analyses of {selected.length} papers
                        and writing one review across them. This normally takes
                        one to three minutes.
                      </p>
                    </div>
                  )}

                  {gen.kind === "unavailable" && (
                    <div className="notice notice--info notice--spaced">
                      <IconAlert size={16} />
                      <div>
                        <p>
                          <strong>The research library is not connected.</strong>{" "}
                          Cross-paper reviews read saved papers, so this needs
                          durable storage.
                        </p>
                      </div>
                    </div>
                  )}

                  {gen.kind === "failed" && (
                    <div className="notice notice--error notice--spaced" role="alert">
                      <IconAlert size={16} />
                      <div>
                        <p>
                          <strong>The review could not be generated.</strong>{" "}
                          {gen.detail}
                        </p>
                        {!gen.exhausted && (
                          <p>
                            <button
                              className="btn btn--sm"
                              onClick={() => void generate()}
                            >
                              Try again
                            </button>
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </section>

      {/* ---------------- single paper ---------------- */}

      <section className="section" aria-labelledby="single-heading">
        <div className="section__head">
          <h2 className="section__title" id="single-heading">
            Single-paper review
          </h2>
        </div>

        <InfoNotice>
          <p>
            <strong>Single-paper scope.</strong> ResearchForge reads the
            related-work and discussion sections of one uploaded paper and
            organises what it finds there. It does not search external
            databases, and it cannot review work the paper never cites.
          </p>
        </InfoNotice>

        {current ? (
          <div className="card" style={{ marginTop: "1rem" }}>
            <div className="card__head">
              <div>
                <h3 className="card__title">{current.data.document.filename}</h3>
                <p className="card__hint">
                  From the paper you analysed in this visit.
                </p>
              </div>
              <Link href="/" className="btn btn--sm">
                Open full analysis
              </Link>
            </div>
            <div className="tabpanel">
              <ReviewSection review={current.data.literature_review} />
            </div>
          </div>
        ) : (
          <div className="card" style={{ marginTop: "1rem" }}>
            <EmptyState
              icon={<IconReview size={28} />}
              title="No paper analysed in this visit"
              actions={
                <Link href="/" className="btn btn--primary">
                  Analyse a paper
                </Link>
              }
            >
              Analyse a paper on the dashboard and its literature review appears
              here. Saved papers keep their own review, readable from My Papers.
            </EmptyState>
          </div>
        )}
      </section>
    </>
  );
}
