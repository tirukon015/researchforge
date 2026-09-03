"use client";

/**
 * Saves a completed analysis into the research library.
 *
 * The analysis is sent, not re-run. It has already been paid for, and
 * re-generating on save would double the cost and could store a different
 * answer than the one on screen.
 *
 * Once saved the button becomes a link to the stored paper rather than
 * reverting to "Save". Leaving it clickable would invite a second identical
 * row, and the library has no way to tell the two apart.
 */

import Link from "next/link";
import { useCallback, useState } from "react";

import { IconAlert, IconCheck, IconSave } from "@/components/Icons";
import { ApiError, savePaper, type AnalysisResponse } from "@/lib/api";

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; id: string }
  | { kind: "unavailable"; detail: string }
  | { kind: "failed"; detail: string };

export default function SavePaperButton({
  data,
  fileSizeBytes,
}: {
  data: AnalysisResponse;
  fileSizeBytes?: number;
}) {
  const [state, setState] = useState<SaveState>({ kind: "idle" });

  const save = useCallback(async () => {
    // Guarding on the state rather than only disabling the button: a double
    // submit from a fast second click would otherwise create two rows.
    if (state.kind === "saving" || state.kind === "saved") return;
    setState({ kind: "saving" });
    try {
      const saved = await savePaper({
        // The document has no bibliographic title yet, so the filename is the
        // honest display name. It is never presented as the paper's title.
        title: data.document.filename,
        filename: data.document.filename,
        file_size_bytes: fileSizeBytes ?? null,
        content_type: "application/pdf",
        document: data.document,
        summary: data.summary,
        research_gaps: data.research_gaps,
        literature_review: data.literature_review,
        model_used: data.model_used,
        // Provenance travels with the save so the stored row records which
        // model really produced it, not merely which one was configured.
        model_provider: data.model_provider,
        fallback_used: data.fallback_used,
        fallback_provider: data.fallback_provider,
        processing_time_ms: data.processing_time_ms,
      });
      setState({ kind: "saved", id: saved.id });
    } catch (error) {
      if (error instanceof ApiError && error.kind === "unavailable") {
        setState({ kind: "unavailable", detail: error.message });
        return;
      }
      setState({
        kind: "failed",
        detail:
          error instanceof ApiError
            ? error.message
            : "The paper could not be saved. Please try again.",
      });
    }
  }, [data, fileSizeBytes, state.kind]);

  if (state.kind === "saved") {
    return (
      <Link href={`/papers/${state.id}`} className="btn btn--sm">
        <IconCheck size={14} />
        Saved. Open in library
      </Link>
    );
  }

  return (
    <div className="saverow">
      <button
        className="btn btn--sm"
        onClick={() => void save()}
        disabled={state.kind === "saving"}
      >
        <IconSave size={14} />
        {state.kind === "saving" ? "Saving" : "Save to library"}
      </button>

      {state.kind === "unavailable" && (
        <span className="saverow__note faint">
          The library is not connected, so this cannot be saved yet.
        </span>
      )}
      {state.kind === "failed" && (
        <span className="saverow__note saverow__note--err" role="alert">
          <IconAlert size={13} />
          {state.detail}
        </span>
      )}
    </div>
  );
}
