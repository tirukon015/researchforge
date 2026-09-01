"use client";

/**
 * Upload and analysis control.
 *
 * Validation happens twice on purpose. Here it is a courtesy - it saves the
 * user a multi-megabyte upload and a two-minute wait to be told the file was
 * never eligible. The backend still checks the real byte count and the actual
 * PDF signature, because a browser-side check is advice, not a guarantee, and
 * `src/api/analyze.py` treats the declared content type as a hint only.
 *
 * The size limit mirrors the backend's MAX_UPLOAD_SIZE_MB default (25). If the
 * deployment raises it, this rejects a file the server would have accepted -
 * the safe direction to be wrong in, since the message names the limit.
 */

import { useCallback, useId, useRef, useState } from "react";

import {
  IconAlert,
  IconFile,
  IconSpark,
  IconTrash,
  IconUpload,
} from "@/components/Icons";
import { useSession } from "@/lib/session";

const MAX_MB = 25;
const MAX_BYTES = MAX_MB * 1024 * 1024;

/** What the request does server-side, in order. */
const STAGES = [
  "Uploading the paper",
  "Extracting text from the PDF",
  "Summarising the research content",
  "Identifying research gaps",
  "Preparing the literature review",
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/** Advice keyed on the error kind, so the user is told what THEY can do. */
function remedyFor(kind: string): string {
  switch (kind) {
    case "offline":
      return "The backend did not respond. Try again shortly.";
    case "rejected":
      return "Choose a different file and try again.";
    case "config":
      return "The server is missing its AI credentials. This needs an administrator, not a different file.";
    case "upstream":
      return "This is a problem with the AI service, not your file. Try again shortly.";
    case "malformed":
      return "The frontend and backend may be running different versions.";
    default:
      return "Try again.";
  }
}

export default function UploadPanel() {
  const { file, setFile, work, elapsed, analyse, clearStaged, health } = useSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();

  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const busy = work.kind === "working";
  const backendDown = health.kind === "down";

  const accept = useCallback(
    (candidate: File | null) => {
      setLocalError(null);
      if (!candidate) return;

      const looksPdf =
        candidate.type === "application/pdf" ||
        candidate.name.toLowerCase().endsWith(".pdf");

      if (!looksPdf) {
        setLocalError(
          `“${candidate.name}” is not a PDF. ResearchForge reads research papers as PDF files.`,
        );
        return;
      }
      if (candidate.size === 0) {
        setLocalError(`“${candidate.name}” is empty.`);
        return;
      }
      if (candidate.size > MAX_BYTES) {
        setLocalError(
          `“${candidate.name}” is ${formatSize(candidate.size)}, over the ${MAX_MB} MB limit.`,
        );
        return;
      }
      setFile(candidate);
    },
    [setFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (busy) return;
      accept(e.dataTransfer.files?.[0] ?? null);
    },
    [accept, busy],
  );

  function remove() {
    clearStaged();
    setLocalError(null);
    // The input keeps its value after a pick, so re-selecting the same file
    // would fire no change event without this.
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <section className="card" aria-labelledby="upload-heading">
      <div className="card__head">
        <div>
          <h2 className="card__title" id="upload-heading">
            Upload a paper
          </h2>
          <p className="card__hint">
            PDF, up to {MAX_MB} MB. Analysis is grounded in this paper alone.
          </p>
        </div>
      </div>

      <div className="card__body">
        {!file && !busy && (
          <div
            className={`drop${dragging ? " drop--over" : ""}${
              backendDown ? " drop--disabled" : ""
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <IconUpload size={26} className="drop__icon" />
            <p className="drop__title">Drag and drop a PDF here</p>
            <p className="drop__hint">or choose a file from your computer</p>

            <input
              ref={inputRef}
              id={inputId}
              type="file"
              className="filepicker-input"
              accept="application/pdf,.pdf"
              disabled={busy}
              onChange={(e) => accept(e.target.files?.[0] ?? null)}
            />
            <label htmlFor={inputId} className="btn btn--primary btn--lg">
              <IconFile size={16} />
              Choose PDF
            </label>
          </div>
        )}

        {file && !busy && (
          <>
            <div className="filecard">
              <IconFile size={22} className="filecard__icon" />
              <div className="filecard__body">
                <div className="filecard__name">{file.name}</div>
                <div className="filecard__meta">
                  PDF · {formatSize(file.size)}
                </div>
              </div>
              <button
                className="btn btn--sm btn--danger"
                onClick={remove}
                aria-label={`Remove ${file.name}`}
              >
                <IconTrash size={14} />
                Remove
              </button>
            </div>

            <div className="btnrow" style={{ marginTop: "1rem" }}>
              <button
                className="btn btn--primary btn--lg"
                onClick={() => void analyse()}
                disabled={backendDown}
              >
                <IconSpark size={16} />
                Analyse paper
              </button>
              <label htmlFor={inputId} className="btn">
                Replace file
              </label>
              <input
                ref={inputRef}
                id={inputId}
                type="file"
                className="filepicker-input"
                accept="application/pdf,.pdf"
                onChange={(e) => accept(e.target.files?.[0] ?? null)}
              />
            </div>
            {backendDown && (
              <p className="card__hint" style={{ marginTop: ".7rem" }}>
                Analysis is unavailable while the backend is unreachable.
              </p>
            )}
          </>
        )}

        {busy && (
          <div className="progress" role="status" aria-live="polite">
            <div className="progress__head">
              <strong>Analysing paper…</strong>
              <span className="progress__elapsed">Elapsed {elapsed}s</span>
            </div>
            {/* Indeterminate on purpose. The API returns one response at the
                end and reports no per-stage progress, so a percentage or a
                stage that ticked over on a timer would be invented. */}
            <div className="progress__bar">
              <span />
            </div>
            <p className="card__hint" style={{ marginTop: ".7rem" }}>
              This normally takes one to three minutes. The steps below are what
              the request performs; the backend does not report which one is
              running, so none is shown as complete.
            </p>
            <ol className="stages">
              {STAGES.map((stage, i) => (
                <li key={stage}>
                  <span className="stages__num">{i + 1}</span>
                  {stage}
                </li>
              ))}
            </ol>
          </div>
        )}

        {localError && (
          <div className="notice notice--error notice--spaced" role="alert">
            <IconAlert size={16} />
            <div>
              <p>
                <strong>That file cannot be analysed.</strong>
              </p>
              <p>{localError}</p>
            </div>
          </div>
        )}

        {work.kind === "failed" && (
          <div className="notice notice--error notice--spaced" role="alert">
            <IconAlert size={16} />
            <div>
              <p>
                <strong>Analysis failed.</strong> {work.error.message}
              </p>
              <p>{remedyFor(work.error.kind)}</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
