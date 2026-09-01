"use client";

/**
 * My Papers.
 *
 * There is no database yet, so there is no library. This page says that
 * plainly rather than showing sample rows: a fabricated list would be the most
 * convincing lie in the product, and the first thing a demo would expose.
 *
 * The card markup below is real and already renders session analyses. When
 * persistence lands, the only change needed is where `records` comes from -
 * the presentation is done.
 */

import Link from "next/link";
import { useMemo } from "react";

import EmptyState from "@/components/EmptyState";
import { IconAlert, IconFile, IconInfo } from "@/components/Icons";
import { useSession } from "@/lib/session";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function PapersPage() {
  const { records, selectRecord } = useSession();

  const rows = useMemo(
    () =>
      records.map((record) => ({
        id: record.id,
        title: record.filename,
        pages: record.data.document.page_count,
        size: formatSize(record.sizeBytes),
        when: record.completedAt,
        gaps: record.data.research_gaps.insufficient_evidence
          ? null
          : record.data.research_gaps.identified_gaps.length,
      })),
    [records],
  );

  return (
    <>
      <header className="pagehead">
        <div>
          <h1 className="pagehead__title">My Papers</h1>
          <p className="pagehead__sub">
            Papers you have analysed. Saving them between visits requires
            persistent storage, which is not built yet.
          </p>
        </div>
      </header>

      <div className="notice notice--info">
        <IconInfo size={16} />
        <div>
          <p>
            <strong>This list is not saved.</strong> ResearchForge is stateless
            today — analyses live in this browser tab and are gone on reload.
            A durable library arrives with the database milestone.
          </p>
        </div>
      </div>

      <section className="section" aria-labelledby="library-heading">
        <div className="section__head">
          <h2 className="section__title" id="library-heading">
            {rows.length > 0 ? "Analysed in this session" : "Library"}
          </h2>
          {rows.length > 0 && (
            <span className="faint" style={{ fontSize: ".8rem" }}>
              {rows.length} paper{rows.length === 1 ? "" : "s"}
            </span>
          )}
        </div>

        {rows.length === 0 ? (
          <div className="card">
            <EmptyState
              art
              title="No saved papers yet"
              actions={
                <Link href="/" className="btn btn--primary">
                  Analyse a paper
                </Link>
              }
            >
              Analysed papers will be listed here — title, filename, date, and
              status — once persistent storage is enabled. Nothing is shown in
              the meantime, because sample entries would misrepresent what the
              application currently stores.
            </EmptyState>
          </div>
        ) : (
          <ul
            style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: ".8rem" }}
          >
            {rows.map((row) => (
              <li key={row.id} className="card">
                <div className="card__body">
                  <div style={{ display: "flex", gap: ".9rem", alignItems: "flex-start" }}>
                    <IconFile size={22} className="filecard__icon" />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div className="filecard__name">{row.title}</div>
                      <div className="filecard__meta">
                        {row.pages} page{row.pages === 1 ? "" : "s"} · {row.size} ·
                        analysed{" "}
                        {row.when.toLocaleString([], {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </div>
                      <div className="tagrow" style={{ marginTop: ".6rem" }}>
                        <span className="badge badge--ok">Analysed</span>
                        {typeof row.gaps === "number" && (
                          <span className="badge">
                            {row.gaps} gap{row.gaps === 1 ? "" : "s"}
                          </span>
                        )}
                        <span className="badge">Session only</span>
                      </div>
                    </div>
                    <Link
                      href="/"
                      className="btn btn--sm"
                      onClick={() => selectRecord(row.id)}
                    >
                      Open analysis
                    </Link>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="section" aria-labelledby="planned-heading">
        <div className="section__head">
          <h2 className="section__title" id="planned-heading">
            What persistence will add
          </h2>
        </div>
        <div className="card">
          <div className="card__body">
            <div className="notice notice--warn" style={{ marginBottom: "1rem" }}>
              <IconAlert size={16} />
              <div>
                <p>
                  Not yet implemented. Listed so the gap between the current
                  build and the plan is visible, not to suggest it exists.
                </p>
              </div>
            </div>
            <ul style={{ margin: 0, paddingLeft: "1.1rem", color: "var(--text-2)" }}>
              <li>Papers saved across sessions and devices</li>
              <li>Re-opening a past analysis without paying for it again</li>
              <li>Searching your own library by title or finding</li>
              <li>Cross-paper literature review over everything you have uploaded</li>
            </ul>
          </div>
        </div>
      </section>
    </>
  );
}
