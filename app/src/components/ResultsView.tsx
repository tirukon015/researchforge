"use client";

/**
 * Renders a completed analysis as three tabbed sections.
 *
 * Presentational only - it receives an `AnalysisResponse` and displays it. It
 * never invents content: where the backend reports insufficient evidence, this
 * says so plainly rather than rendering an empty section that looks like a bug
 * or, worse, like an answer.
 */

import { useState } from "react";

import type { AnalysisResponse } from "@/lib/api";

type TabId = "summary" | "gaps" | "review";

const TABS: { id: TabId; label: string }[] = [
  { id: "summary", label: "Summary" },
  { id: "gaps", label: "Research Gaps" },
  { id: "review", label: "Literature Review" },
];

/** A titled list. Renders nothing at all when there is nothing to show. */
function ListBlock({ title, items }: { title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="block">
      <h4>{title}</h4>
      <ul>
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function Field({ title, value }: { title: string; value: string }) {
  if (!value) return null;
  return (
    <div className="block">
      <h4>{title}</h4>
      <p>{value}</p>
    </div>
  );
}

/** Shown when the model reported it could not support a section from the paper. */
function EvidenceNotice({ children }: { children: React.ReactNode }) {
  return (
    <div className="notice notice--evidence">
      <strong>Insufficient evidence.</strong> {children}
    </div>
  );
}

export default function ResultsView({ data }: { data: AnalysisResponse }) {
  const [tab, setTab] = useState<TabId>("summary");
  const { document: doc, summary, research_gaps: gaps, literature_review: review } = data;

  return (
    <section className="results">
      <header className="results__head">
        <div>
          <h2 className="results__title">{doc.filename}</h2>
          <p className="results__meta">
            {doc.page_count} page{doc.page_count === 1 ? "" : "s"} ·{" "}
            {doc.extracted_characters.toLocaleString()} characters extracted ·{" "}
            {doc.chunk_count === 1
              ? "analysed as a single document"
              : `analysed in ${doc.chunk_count} sections`}
          </p>
        </div>
        <span className="badge badge--model" title="Model that produced this analysis">
          {data.model_used}
        </span>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={`tab${tab === t.id ? " tab--active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="tabpanel" role="tabpanel">
        {tab === "summary" && (
          <>
            <Field title="Research problem and background" value={summary.research_problem} />
            <Field title="Methodology" value={summary.methodology} />
            <ListBlock title="Key findings" items={summary.key_findings} />
            <Field title="Conclusion" value={summary.conclusion} />
            {summary.insufficient_evidence.length > 0 && (
              <EvidenceNotice>
                The paper did not contain enough information for:{" "}
                {summary.insufficient_evidence.join(", ")}.
              </EvidenceNotice>
            )}
          </>
        )}

        {tab === "gaps" && (
          <>
            {gaps.insufficient_evidence ? (
              <EvidenceNotice>
                {gaps.evidence_note ||
                  "This paper does not contain enough material to support a gap analysis."}
              </EvidenceNotice>
            ) : (
              <>
                <ListBlock
                  title="Limitations stated by the authors"
                  items={gaps.stated_limitations}
                />
                {gaps.identified_gaps.length > 0 && (
                  <div className="block">
                    <h4>Identified research gaps</h4>
                    {gaps.identified_gaps.map((g, i) => (
                      <article className="gap" key={i}>
                        <h5>{g.gap}</h5>
                        <p className="gap__why">
                          <span className="gap__label">Why it matters</span>
                          {g.why_it_matters}
                        </p>
                        {/* Evidence is what separates an identified gap from an
                            invented one, so it is always shown, never hidden. */}
                        <blockquote className="gap__evidence">
                          <span className="gap__label">Evidence from the paper</span>
                          {g.evidence}
                        </blockquote>
                      </article>
                    ))}
                  </div>
                )}
              </>
            )}
          </>
        )}

        {tab === "review" && (
          <>
            <div className="notice notice--scope">{review.scope_note}</div>
            {review.insufficient_evidence ? (
              <EvidenceNotice>
                This paper discusses too little prior work to review.
              </EvidenceNotice>
            ) : (
              <>
                <ListBlock title="Major themes" items={review.major_themes} />
                <ListBlock title="Relevant findings" items={review.relevant_findings} />
                <ListBlock title="Comparisons between studies" items={review.comparisons} />
                <ListBlock title="Research trends" items={review.research_trends} />
                <ListBlock title="Limitations of prior work" items={review.limitations} />
                <ListBlock title="Possible research directions" items={review.future_directions} />
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
