"use client";

/**
 * Literature Review.
 *
 * The honesty problem this page exists to solve: "literature review" normally
 * means a survey across many papers, and a page with that title invites the
 * reader to assume ResearchForge searched a corpus. It did not. The review is
 * written from the prior work discussed INSIDE the single uploaded paper, and
 * the page says so above the content rather than in a footnote.
 *
 * The cross-paper version needs retrieval over a stored corpus - the database
 * and embedding milestones. It is described as unbuilt, with no placeholder
 * search box implying otherwise.
 */

import Link from "next/link";

import { ReviewSection } from "@/components/AnalysisSections";
import EmptyState from "@/components/EmptyState";
import { IconInfo, IconReview } from "@/components/Icons";
import { useSession } from "@/lib/session";

export default function LiteratureReviewPage() {
  const { current } = useSession();

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">Literature Review</h1>
          <p className="pagehead__sub">
            Generated from the prior work discussed within the paper you
            analysed, not from a search across a body of literature.
          </p>
        </div>
      </header>

      <div className="notice notice--info">
        <IconInfo size={16} />
        <div>
          <p>
            <strong>Single-paper scope.</strong> ResearchForge reads the
            related-work and discussion sections of one uploaded paper and
            organises what it finds there. It does not search external
            databases, and it cannot review work the paper never cites.
          </p>
        </div>
      </div>

      {current ? (
        <section className="section" aria-labelledby="review-heading">
          <div className="section__head">
            <h2 className="section__title" id="review-heading">
              From {current.data.document.filename}
            </h2>
            <Link href="/" className="btn btn--sm">
              Open full analysis
            </Link>
          </div>
          <div className="card">
            <div className="tabpanel">
              <ReviewSection review={current.data.literature_review} />
            </div>
          </div>
        </section>
      ) : (
        <section className="section">
          <div className="card">
            <EmptyState
              icon={<IconReview size={30} />}
              title="No paper analysed yet"
              actions={
                <Link href="/" className="btn btn--primary">
                  Analyse a paper
                </Link>
              }
            >
              Analyse a paper on the dashboard and its literature review will
              appear here. The review is produced in the same request as the
              summary and gap analysis.
            </EmptyState>
          </div>
        </section>
      )}

      <section className="section" aria-labelledby="cross-heading">
        <div className="section__head">
          <h2 className="section__title" id="cross-heading">
            Cross-paper review
          </h2>
          <span className="badge">Not built</span>
        </div>
        <div className="card">
          <div className="card__body">
            <p className="muted" style={{ marginTop: 0 }}>
              Reviewing themes across everything you have uploaded needs three
              pieces that do not exist yet: papers stored durably, their text
              embedded for semantic search, and retrieval that pulls the
              relevant passages from across the corpus before the model writes.
            </p>
            <p className="muted" style={{ marginBottom: 0 }}>
              The decisions are recorded (Jina{" "}
              <code>jina-embeddings-v3</code> at 1024 dimensions, with pgvector
              for storage), but none of it is wired up, so nothing on this page
              draws from more than the single paper above.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}
