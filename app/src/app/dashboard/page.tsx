"use client";

/**
 * Dashboard.
 *
 * Ordered so the next action is the first thing read: brand, then Upload, then
 * what has happened, then how it works.
 *
 * Every figure in the overview comes from the database. When the library is
 * not connected the cards say so instead of showing zeros, because zero is a
 * claim ("you have no papers") that a deployment with nowhere to store papers
 * cannot make.
 */

import Link from "next/link";
import { useCallback, useRef } from "react";

import BackendStatus from "@/components/BackendStatus";
import EmptyState from "@/components/EmptyState";
import {
  IconGap,
  IconPapers,
  IconReview,
  IconStack,
  IconUpload,
} from "@/components/Icons";
import ResultsView from "@/components/ResultsView";
import UploadPanel from "@/components/UploadPanel";
import { useLibraryStats, useMostRecentPaper } from "@/lib/library";
import type { AnalysisResponse, PaperDetail } from "@/lib/api";
import { useSession } from "@/lib/session";

const WORKFLOW = [
  {
    title: "Upload",
    body: "Drop in a PDF. Text is extracted server side, and a scanned paper with no text layer is rejected rather than guessed at.",
  },
  {
    title: "Analyse",
    body: "The paper goes to Gemini in three separate reasoning passes, each constrained to a schema and validated on return.",
  },
  {
    title: "Discover",
    body: "Read the summary and the research gaps, each gap shown with the evidence in the paper that supports it.",
  },
  {
    title: "Review",
    body: "Save the paper to your library, then build a literature review from one paper or across several.",
  },
];

/**
 * A stored paper, reshaped as an analysis result.
 *
 * `PaperDetail` and `AnalysisResponse` carry the same three sections but
 * differ at the edges: the stored row keeps its document facts as columns,
 * while the live response nests them under `document`. This adapts one to the
 * other so `ResultsView` renders both without knowing where the data came
 * from.
 *
 * Only called where `summary` is non-null, which the caller checks.
 */
function savedAsAnalysis(paper: PaperDetail): AnalysisResponse {
  return {
    document: {
      filename: paper.filename,
      page_count: paper.page_count ?? 0,
      extracted_characters: paper.extracted_characters ?? 0,
      chunk_count: paper.chunk_count ?? 1,
      truncated: paper.truncated ?? false,
    },
    summary: paper.summary!,
    research_gaps: paper.research_gaps!,
    literature_review: paper.literature_review!,
    model_used: paper.model_used ?? "",
    model_provider: paper.model_provider,
    fallback_used: paper.fallback_used,
    fallback_provider: paper.fallback_provider,
    processing_time_ms: paper.processing_time_ms,
  };
}

export default function DashboardPage() {
  const { records, current } = useSession();
  const { state: stats } = useLibraryStats();
  // The saved library, so a returning visitor is not told "No analysis yet"
  // while the counter above says they have two.
  const { state: recent } = useMostRecentPaper();
  const uploadRef = useRef<HTMLDivElement>(null);

  const focusUpload = useCallback(() => {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // One helper for all four cards. A real count when the library answered, the
  // word "Not connected" when it did not, and a dash while it is still loading.
  const figure = (value: number | undefined) => {
    if (stats.kind === "ready") return String(value ?? 0);
    if (stats.kind === "loading") return "";
    return "Not connected";
  };
  const unavailable = stats.kind === "unavailable" || stats.kind === "failed";

  return (
    <>
      <header className="hero">
        <div className="hero__text">
          <span className="hero__eyebrow">AI Research Assistant</span>
          <h1 className="hero__title">ResearchForge</h1>
          <p className="hero__sub">
            Upload academic papers, analyse them, identify research gaps, and
            build literature-review insights. Every result is grounded in the
            paper you provide.
          </p>
          <div className="btnrow hero__actions">
            <button className="btn btn--primary btn--lg" onClick={focusUpload}>
              <IconUpload size={16} />
              Upload research paper
            </button>
            <Link href="/papers" className="btn">
              My Papers
            </Link>
            <Link href="/literature-review" className="btn">
              Literature Review
            </Link>
          </div>
        </div>
        <BackendStatus />
      </header>

      <div ref={uploadRef} style={{ scrollMarginTop: "5rem" }}>
        <UploadPanel />
      </div>

      <section className="section" aria-labelledby="overview-heading">
        <div className="section__head">
          <h2 className="section__title" id="overview-heading">
            Overview
          </h2>
          {unavailable && (
            <span className="faint" style={{ fontSize: ".8rem" }}>
              Library not connected
            </span>
          )}
        </div>

        <div className="stats">
          <StatCard
            icon={<IconPapers size={16} />}
            label="Papers analysed"
            value={figure(stats.kind === "ready" ? stats.data.papers_analysed : undefined)}
            note={
              unavailable
                ? "Counts appear once durable storage is connected."
                : "Analyses stored in your library."
            }
            loading={stats.kind === "loading"}
          />
          <StatCard
            icon={<IconGap size={16} />}
            label="Research gaps"
            value={figure(
              stats.kind === "ready" ? stats.data.research_gaps_found : undefined,
            )}
            note={
              unavailable
                ? "Gaps are counted from saved analyses."
                : "Only gaps the analysis could support with evidence."
            }
            loading={stats.kind === "loading"}
          />
          <StatCard
            icon={<IconReview size={16} />}
            label="Literature reviews"
            value={figure(
              stats.kind === "ready" ? stats.data.literature_reviews : undefined,
            )}
            note={
              unavailable
                ? "Saved reviews will be counted here."
                : "Reviews saved across your papers."
            }
            loading={stats.kind === "loading"}
          />
          <StatCard
            icon={<IconStack size={16} />}
            label="Saved papers"
            value={figure(stats.kind === "ready" ? stats.data.saved_papers : undefined)}
            note={
              unavailable
                ? "Papers are saved once storage is connected."
                : "Papers in your research library."
            }
            loading={stats.kind === "loading"}
          />
        </div>
      </section>

      <section className="section" aria-labelledby="recent-heading">
        <div className="section__head">
          <h2 className="section__title" id="recent-heading">
            Recent analysis
          </h2>
          {records.length > 0 && (
            <Link href="/papers" className="btn btn--sm">
              View all papers
            </Link>
          )}
        </div>

        {/* Three cases, in the order they are true:
              1. an analysis run in THIS visit - the freshest thing there is;
              2. otherwise the most recently SAVED paper, so a reload does not
                 erase the page;
              3. otherwise a genuinely empty library.
            Case 2 is the fix: the old code jumped from 1 to 3 and printed
            "No analysis yet" beside a stat card counting saved papers. */}
        {current ? (
          <ResultsView
            data={current.data}
            completedAt={current.completedAt}
            fileSizeBytes={current.sizeBytes}
          />
        ) : recent.kind === "ready" && recent.data && recent.data.summary ? (
          <>
            <p className="card__hint" style={{ marginBottom: "0.75rem" }}>
              Your most recently saved paper. Upload another above to analyse
              something new.
            </p>
            <ResultsView
              data={savedAsAnalysis(recent.data)}
              completedAt={new Date(recent.data.created_at)}
              fileSizeBytes={recent.data.file_size_bytes ?? undefined}
            />
          </>
        ) : recent.kind === "loading" ? (
          <div className="skeleton">
            <div className="skeleton__line skeleton__line--title" />
            <div className="skeleton__line" />
            <div className="skeleton__line" />
          </div>
        ) : (
          <div className="card">
            <EmptyState
              art
              title="No analysis yet"
              actions={
                <button className="btn btn--primary" onClick={focusUpload}>
                  <IconUpload size={16} />
                  Upload your first research paper
                </button>
              }
            >
              Upload a PDF above and the summary, research gaps and literature
              review will open here. Save it afterwards to keep it in your
              library.
            </EmptyState>
          </div>
        )}
      </section>

      <section className="section" aria-labelledby="workflow-heading">
        <div className="section__head">
          <h2 className="section__title" id="workflow-heading">
            How ResearchForge works
          </h2>
        </div>
        <ol className="steps">
          {WORKFLOW.map((step, i) => (
            <li className="step" key={step.title}>
              <span className="step__n">{i + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.body}</p>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

function StatCard({
  icon,
  label,
  value,
  note,
  loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  note: string;
  loading: boolean;
}) {
  return (
    <article className="stat">
      <div className="stat__top">
        {icon}
        <span className="stat__label">{label}</span>
      </div>
      <div className={`stat__value${value === "Not connected" ? " stat__value--muted" : ""}`}>
        {loading ? <span className="stat__pending" aria-label="Loading" /> : value}
      </div>
      <p className="stat__note">{note}</p>
    </article>
  );
}
