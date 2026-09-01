"use client";

/**
 * Dashboard.
 *
 * Ordered so the next action is the first thing read: brand, then Upload, then
 * what has happened, then how it works. Upload is never more than one screen
 * from the top and is never behind a menu.
 *
 * Every statistic on this page is counted from analyses this browser session
 * actually completed. Nothing is seeded, sampled, or estimated - with no
 * database, the honest number is usually zero, and zero with an explanation is
 * worth more to a reader than a plausible-looking figure.
 */

import Link from "next/link";
import { useCallback, useRef } from "react";

import BackendStatus from "@/components/BackendStatus";
import EmptyState from "@/components/EmptyState";
import {
  IconAlert,
  IconGap,
  IconPapers,
  IconReview,
  IconUpload,
} from "@/components/Icons";
import ResultsView from "@/components/ResultsView";
import UploadPanel from "@/components/UploadPanel";
import { sessionStats, useSession } from "@/lib/session";

const IS_LOCAL_DEV = process.env.NODE_ENV === "development";

const WORKFLOW = [
  {
    title: "Upload a paper",
    body: "Drop in a PDF. Text is extracted server-side with pypdf; scanned images are rejected rather than guessed at.",
  },
  {
    title: "Analyse",
    body: "The paper is sent to Gemini in three separate reasoning passes — summary, gaps, then literature review.",
  },
  {
    title: "Read the workspace",
    body: "Results open in tabs with the evidence each gap rests on, so every claim can be traced back to the paper.",
  },
];

export default function DashboardPage() {
  const { health, records, current, work } = useSession();
  const uploadRef = useRef<HTMLDivElement>(null);

  const stats = sessionStats(records);
  const busy = work.kind === "working";

  const focusUpload = useCallback(() => {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <>
      <header className="pagehead">
        <div>
          <span className="pagehead__eyebrow">AI Research Assistant</span>
          <h1 className="pagehead__title">ResearchForge</h1>
          <p className="pagehead__sub">
            Upload a research paper to generate a summary, identify research
            gaps, and produce a literature review — each grounded in the paper
            you provide.
          </p>
        </div>
        <div className="btnrow">
          <BackendStatus />
          <button className="btn btn--primary" onClick={focusUpload} disabled={busy}>
            <IconUpload size={16} />
            Upload paper
          </button>
        </div>
      </header>

      {health.kind === "down" && (
        <div className="notice notice--error" role="alert">
          <IconAlert size={16} />
          <div>
            <p>
              <strong>The backend is not reachable.</strong> {health.detail}{" "}
              Analysis is unavailable until it responds.
            </p>
            <p>
              {IS_LOCAL_DEV ? (
                <>
                  Start it with{" "}
                  <code>uvicorn src.main:app --reload --port 8000</code>.
                </>
              ) : (
                <>Try again in a moment; if it persists, the deployment needs attention.</>
              )}
            </p>
          </div>
        </div>
      )}

      <div ref={uploadRef} style={{ scrollMarginTop: "1rem", marginTop: "1.5rem" }}>
        <UploadPanel />
      </div>

      <section className="section" aria-labelledby="overview-heading">
        <div className="section__head">
          <h2 className="section__title" id="overview-heading">
            Overview
          </h2>
          <span className="faint" style={{ fontSize: ".8rem" }}>
            This browser session
          </span>
        </div>

        <div className="stats">
          <article className="stat">
            <div className="stat__top">
              <IconPapers size={16} />
              <span className="stat__label">Papers analysed</span>
            </div>
            <div className="stat__value">{stats.papersAnalysed}</div>
            <p className="stat__note">
              {stats.papersAnalysed === 0
                ? "Your analysed papers will appear here once you upload one."
                : "Counted from analyses completed in this session."}
            </p>
          </article>

          <article className="stat">
            <div className="stat__top">
              <IconGap size={16} />
              <span className="stat__label">Research gaps found</span>
            </div>
            <div className="stat__value">{stats.gapsFound}</div>
            <p className="stat__note">
              {stats.papersAnalysed === 0
                ? "Gaps identified from your papers will be counted here."
                : "Only gaps the analysis could support with evidence are counted."}
            </p>
          </article>

          <article className="stat">
            <div className="stat__top">
              <IconReview size={16} />
              <span className="stat__label">Literature reviews</span>
            </div>
            <div className="stat__value">{stats.reviews}</div>
            <p className="stat__note">
              {stats.papersAnalysed === 0
                ? "One review is produced per analysed paper."
                : "Reviews the analysis had enough prior work to write."}
            </p>
          </article>

          <article className="stat">
            <div className="stat__top">
              <IconPapers size={16} />
              <span className="stat__label">Saved library</span>
            </div>
            <div className="stat__value faint">—</div>
            <p className="stat__note">
              Not yet available. Counts across sessions need the database
              milestone; see <Link href="/papers">My Papers</Link>.
            </p>
          </article>
        </div>
      </section>

      <section className="section" aria-labelledby="recent-heading">
        <div className="section__head">
          <h2 className="section__title" id="recent-heading">
            Recent analysis
          </h2>
          {records.length > 1 && (
            <span className="faint" style={{ fontSize: ".8rem" }}>
              {records.length} in this session
            </span>
          )}
        </div>

        {current ? (
          <ResultsView data={current.data} completedAt={current.completedAt} />
        ) : (
          <div className="card">
            <EmptyState
              art
              title="No analysis yet"
              actions={
                <button className="btn btn--primary" onClick={focusUpload}>
                  <IconUpload size={16} />
                  Upload paper
                </button>
              }
            >
              Upload a PDF above and the summary, research gaps, and literature
              review will open here. Results are held for this browser session
              only — saving them between visits needs the database milestone.
            </EmptyState>
          </div>
        )}
      </section>

      {records.length > 1 && (
        <section className="section" aria-labelledby="session-heading">
          <div className="section__head">
            <h2 className="section__title" id="session-heading">
              Earlier in this session
            </h2>
          </div>
          <div className="card">
            <div className="card__body">
              <SessionList />
            </div>
          </div>
        </section>
      )}

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

/** Switcher for the other analyses run in this session. */
function SessionList() {
  const { records, current, selectRecord } = useSession();

  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: ".5rem" }}>
      {records.map((record) => {
        const isCurrent = current?.id === record.id;
        return (
          <li key={record.id} className="filecard">
            <IconPapers size={20} className="filecard__icon" />
            <div className="filecard__body">
              <div className="filecard__name">{record.filename}</div>
              <div className="filecard__meta">
                {record.data.document.page_count} pages ·{" "}
                {record.completedAt.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
            {isCurrent ? (
              <span className="badge badge--accent">Open</span>
            ) : (
              <button className="btn btn--sm" onClick={() => selectRecord(record.id)}>
                Open
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
