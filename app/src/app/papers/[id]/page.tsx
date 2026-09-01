"use client";

/**
 * One saved paper, loaded from the database by id.
 *
 * This route is what makes persistence real. It reads from storage rather than
 * from anything the browser happens to be holding, so it works after a
 * refresh, in a new tab, and on another device.
 */

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useState } from "react";

import {
  GapsSection,
  ReviewSection,
  SummarySection,
} from "@/components/AnalysisSections";
import EmptyState from "@/components/EmptyState";
import { IconAlert, IconBack, IconPlus, IconTrash } from "@/components/Icons";
import { LibraryError, LibraryUnavailable, LoadingRows } from "@/components/LibraryUI";
import { ApiError, deletePaper } from "@/lib/api";
import { formatDate, formatSize, usePaper, useSelection } from "@/lib/library";

type TabId = "summary" | "gaps" | "review" | "details";

export default function PaperDetailPage() {
  const params = useParams<{ id: string }>();
  const id = typeof params?.id === "string" ? params.id : null;
  const router = useRouter();

  const { state, reload } = usePaper(id);
  const { isSelected, toggle } = useSelection();
  const [tab, setTab] = useState<TabId>("summary");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remove = useCallback(async () => {
    if (!id || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await deletePaper(id);
      router.push("/papers");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "That paper could not be deleted. Please try again.",
      );
      setDeleting(false);
    }
  }, [id, deleting, router]);

  if (state.kind === "unavailable") return <LibraryUnavailable detail={state.detail} />;
  if (state.kind === "loading") return <LoadingRows rows={2} />;

  if (state.kind === "failed") {
    if (state.error.kind === "notfound") {
      return (
        <div className="card">
          <EmptyState
            icon={<IconAlert size={28} />}
            title="That paper is not in your library"
            actions={
              <Link href="/papers" className="btn btn--primary">
                Back to My Papers
              </Link>
            }
          >
            It may have been deleted, or the link may be out of date.
          </EmptyState>
        </div>
      );
    }
    return <LibraryError message={state.error.message} onRetry={() => void reload()} />;
  }

  const paper = state.data;
  const selected = isSelected(paper.id);
  const hasAnalysis = paper.summary !== null;

  const TABS: { id: TabId; label: string; count?: number | null }[] = [
    {
      id: "summary",
      label: "Summary",
      count: paper.summary?.key_findings.length ?? null,
    },
    {
      id: "gaps",
      label: "Research Gaps",
      count: paper.research_gaps?.insufficient_evidence
        ? null
        : (paper.research_gaps?.identified_gaps.length ?? null),
    },
    { id: "review", label: "Literature Review" },
    { id: "details", label: "Paper Details" },
  ];

  return (
    <>
      <div className="btnrow" style={{ marginBottom: "1rem" }}>
        <Link href="/papers" className="btn btn--sm btn--ghost">
          <IconBack size={14} />
          Back to My Papers
        </Link>
      </div>

      <header className="pagehead">
        <div style={{ minWidth: 0 }}>
          <h1 className="pagehead__title">{paper.title}</h1>
          <p className="pagehead__sub">
            {paper.filename}
            {paper.page_count != null && ` · ${paper.page_count} pages`}
            {` · ${formatSize(paper.file_size_bytes)} · saved ${formatDate(paper.created_at)}`}
          </p>
          <div className="tagrow" style={{ marginTop: ".6rem" }}>
            <span className={paper.status === "ready" ? "badge badge--ok" : "badge"}>
              {paper.status === "ready" ? "Analysed" : paper.status}
            </span>
            {paper.truncated && <span className="badge">Truncated</span>}
            {paper.model_used && (
              <span className="badge badge--mono">{paper.model_used}</span>
            )}
          </div>
        </div>

        <div className="btnrow">
          <button
            className={`btn btn--sm${selected ? "" : " btn--primary"}`}
            onClick={() =>
              toggle({
                id: paper.id,
                title: paper.title,
                filename: paper.filename,
                status: paper.status,
                page_count: paper.page_count,
                file_size_bytes: paper.file_size_bytes,
                created_at: paper.created_at,
                updated_at: paper.updated_at,
                has_analysis: hasAnalysis,
                gap_count: paper.research_gaps?.identified_gaps.length ?? null,
              })
            }
          >
            <IconPlus size={14} />
            {selected ? "Remove from review" : "Add to review"}
          </button>
          <button
            className="btn btn--sm btn--danger"
            onClick={() => void remove()}
            disabled={deleting}
          >
            <IconTrash size={14} />
            {deleting ? "Deleting" : "Delete"}
          </button>
        </div>
      </header>

      {error && (
        <div className="notice notice--error" role="alert">
          <IconAlert size={16} />
          <div>
            <p>{error}</p>
          </div>
        </div>
      )}

      {!hasAnalysis ? (
        <div className="card">
          <EmptyState
            icon={<IconAlert size={28} />}
            title="No analysis is stored for this paper"
          >
            The paper is in your library, but no analysis was saved with it.
            Analyse it again from the dashboard to produce one.
          </EmptyState>
        </div>
      ) : (
        <section className="card">
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
            {tab === "summary" && paper.summary && (
              <SummarySection summary={paper.summary} />
            )}
            {tab === "gaps" && paper.research_gaps && (
              <GapsSection gaps={paper.research_gaps} />
            )}
            {tab === "review" && paper.literature_review && (
              <ReviewSection review={paper.literature_review} />
            )}
            {tab === "details" && (
              <dl className="dl">
                <div>
                  <dt>Filename</dt>
                  <dd>{paper.filename}</dd>
                </div>
                <div>
                  <dt>Pages</dt>
                  <dd>{paper.page_count ?? "Not recorded"}</dd>
                </div>
                <div>
                  <dt>Characters extracted</dt>
                  <dd>
                    {paper.extracted_characters?.toLocaleString() ?? "Not recorded"}
                  </dd>
                </div>
                <div>
                  <dt>File size</dt>
                  <dd>{formatSize(paper.file_size_bytes)}</dd>
                </div>
                <div>
                  <dt>Analysed as</dt>
                  <dd>
                    {paper.chunk_count === 1
                      ? "A single document"
                      : `${paper.chunk_count ?? "unknown"} sections`}
                  </dd>
                </div>
                <div>
                  <dt>Model</dt>
                  <dd>{paper.model_used ?? "Not recorded"}</dd>
                </div>
                <div>
                  <dt>Saved</dt>
                  <dd>{formatDate(paper.created_at)}</dd>
                </div>
                <div>
                  <dt>Content truncated</dt>
                  <dd>{paper.truncated ? "Yes" : "No"}</dd>
                </div>
              </dl>
            )}
          </div>
        </section>
      )}
    </>
  );
}
