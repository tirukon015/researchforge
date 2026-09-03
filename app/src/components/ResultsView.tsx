"use client";

/**
 * The analysis workspace: one completed analysis, organised for reading.
 *
 * Replaces the original three-plain-text-boxes layout. The paper's identity and
 * shape stay pinned in the header while the tabs change, because "which paper
 * am I reading, and how much of it was actually read" is the context every
 * other section is judged against.
 *
 * Presentational only - it receives an `AnalysisResponse` and displays it.
 * The section renderers in `AnalysisSections` are shared with the Literature
 * Review page so one result never renders two different ways.
 */

import { useState } from "react";

import {
  GapsSection,
  PaperInfoSection,
  ReviewSection,
  SummarySection,
} from "@/components/AnalysisSections";
import SavePaperButton from "@/components/SavePaperButton";
import type { AnalysisResponse } from "@/lib/api";

type TabId = "summary" | "gaps" | "review" | "paper";

/**
 * Provider keys to the names a reader recognises.
 *
 * Mirrors DISPLAY_NAMES in src/rag/llm/router.py. Kept as a lookup with a
 * fallback to the raw key so a provider added on the server later shows its
 * key rather than blanking the badge.
 */
const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Claude",
  groq: "Groq Qwen 3.6 27B",
  // Retired from the active workflow, but stored analyses still name it.
  gemini: "Gemini",
};

export default function ResultsView({
  data,
  completedAt,
  fileSizeBytes,
}: {
  data: AnalysisResponse;
  completedAt?: Date;
  fileSizeBytes?: number;
}) {
  const [tab, setTab] = useState<TabId>("summary");
  const { document: doc, summary, research_gaps: gaps, literature_review: review } = data;

  // Counts sit on the tabs so the shape of the result is visible before
  // opening anything. A section the model could not support shows no count
  // rather than a zero that would read as "we looked and found none".
  const gapCount = gaps.insufficient_evidence ? null : gaps.identified_gaps.length;
  const reviewThemes = review.insufficient_evidence ? null : review.major_themes.length;

  const TABS: { id: TabId; label: string; count?: number | null }[] = [
    { id: "summary", label: "Summary", count: summary.key_findings.length },
    { id: "gaps", label: "Research Gaps", count: gapCount },
    { id: "review", label: "Literature Review", count: reviewThemes },
    { id: "paper", label: "Paper Information" },
  ];

  return (
    <section className="card" aria-labelledby="analysis-heading">
      <header className="card__head">
        <div style={{ minWidth: 0 }}>
          <h2 className="card__title" id="analysis-heading">
            {doc.filename}
          </h2>
          <p className="card__hint">
            {doc.page_count} page{doc.page_count === 1 ? "" : "s"} ·{" "}
            {doc.extracted_characters.toLocaleString()} characters extracted ·{" "}
            {doc.chunk_count === 1
              ? "analysed as a single document"
              : `analysed in ${doc.chunk_count} sections`}
            {completedAt && (
              <>
                {" · "}
                analysed{" "}
                {completedAt.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </>
            )}
          </p>
        </div>
        <div className="results__actions">
          <div className="tagrow">
            {doc.truncated && <span className="badge">Truncated</span>}
            {/* WHICH provider produced this, not which one was configured. If
                the primary was rate limited and the other one wrote the
                result, this names the one that actually wrote it - crediting
                a model that never saw the paper would be a false provenance
                record. Absent on analyses stored before this was recorded,
                which is why it is conditional rather than defaulted. */}
            {data.model_provider && (
              <span className="badge badge--accent" title="Provider that produced this analysis">
                {PROVIDER_LABELS[data.model_provider] ?? data.model_provider}
              </span>
            )}
            {data.fallback_used && (
              <span
                className="badge"
                title="The primary provider was unavailable, so the other one produced this analysis"
              >
                Fallback used
              </span>
            )}
            <span className="badge badge--mono" title="Model that produced this analysis">
              {data.model_used}
            </span>
          </div>
          {/* Saving is what turns a session result into a library entry. It is
              offered here, beside the analysis it would save, rather than on a
              separate screen. */}
          <SavePaperButton data={data} fileSizeBytes={fileSizeBytes} />
        </div>
      </header>

      <nav className="tabs" role="tablist" aria-label="Analysis sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={`tab${tab === t.id ? " tab--active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {typeof t.count === "number" && t.count > 0 && (
              <span className="faint"> ({t.count})</span>
            )}
          </button>
        ))}
      </nav>

      <div className="tabpanel" role="tabpanel">
        {tab === "summary" && <SummarySection summary={summary} />}
        {tab === "gaps" && <GapsSection gaps={gaps} />}
        {tab === "review" && <ReviewSection review={review} />}
        {tab === "paper" && <PaperInfoSection data={data} />}
      </div>
    </section>
  );
}
