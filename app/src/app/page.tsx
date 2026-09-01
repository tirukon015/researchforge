"use client";

/**
 * ResearchForge - main workflow page.
 *
 * Select a PDF -> analyse -> read the summary, research gaps, and literature
 * review. One screen, because the workflow is genuinely one step.
 *
 * Everything shown here comes from the backend. Nothing is mocked, and features
 * that are not built yet are named as not built rather than stubbed with
 * placeholder output.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import ResultsView from "@/components/ResultsView";
import {
  analyzePaper,
  API_BASE_LABEL,
  ApiError,
  checkHealth,
  type AnalysisResponse,
  type HealthPayload,
} from "@/lib/api";

// The deployed backend is part of this same deployment, so "start it yourself"
// is advice only a developer can act on. Showing it in production would tell a
// visitor to fix a machine they do not have.
const IS_LOCAL_DEV = process.env.NODE_ENV === "development";

type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthPayload }
  | { kind: "down"; detail: string };

type WorkState =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "done"; data: AnalysisResponse }
  | { kind: "failed"; error: ApiError };

const ACCEPTED = "application/pdf";

/** Advice keyed on the error kind, so the user is told what THEY can do. */
function remedyFor(error: ApiError): string {
  switch (error.kind) {
    case "offline":
      return "Start the backend, then try again.";
    case "rejected":
      return "Choose a different file and try again.";
    case "config":
      return "The server is missing its AI credentials. This needs an administrator, not a different file.";
    case "upstream":
      return "This is a problem with the AI service, not your file. Try again shortly.";
    case "malformed":
      return "The frontend and backend may be running different versions.";
  }
}

export default function Home() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });
  const [file, setFile] = useState<File | null>(null);
  const [work, setWork] = useState<WorkState>({ kind: "idle" });
  const [elapsed, setElapsed] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const refreshHealth = useCallback(async () => {
    setHealth({ kind: "loading" });
    try {
      setHealth({ kind: "ok", data: await checkHealth() });
    } catch (error) {
      setHealth({
        kind: "down",
        detail: error instanceof ApiError ? error.message : "Backend unreachable.",
      });
    }
  }, []);

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  // A live counter during analysis. Multi-minute waits are normal here, and a
  // spinner with no elapsed time reads as a hang.
  useEffect(() => {
    if (work.kind !== "working") return;
    setElapsed(0);
    const started = Date.now();
    const timer = setInterval(
      () => setElapsed(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, [work.kind]);

  function pick(selected: File | null) {
    setFile(selected);
    // Clear a previous result so the screen never shows one paper's analysis
    // next to another paper's filename.
    setWork({ kind: "idle" });
  }

  async function run() {
    if (!file) return;
    setWork({ kind: "working" });
    try {
      const data = await analyzePaper(file);
      setWork({ kind: "done", data });
    } catch (error) {
      setWork({
        kind: "failed",
        error:
          error instanceof ApiError
            ? error
            : new ApiError("upstream", "An unexpected error occurred."),
      });
    }
  }

  function reset() {
    setFile(null);
    setWork({ kind: "idle" });
    if (inputRef.current) inputRef.current.value = "";
  }

  const busy = work.kind === "working";

  return (
    <main>
      <header className="masthead">
        <div>
          <h1>ResearchForge</h1>
          <p className="tagline">
            AI Research Paper Assistant — upload a paper to generate a summary,
            identify research gaps, and produce a literature review.
          </p>
        </div>
        <button
          className="health"
          onClick={() => void refreshHealth()}
          disabled={health.kind === "loading"}
          title={`Backend: ${API_BASE_LABEL}`}
        >
          <span
            className={`dot ${
              health.kind === "ok"
                ? "dot--ok"
                : health.kind === "down"
                  ? "dot--err"
                  : "dot--wait"
            }`}
          />
          {health.kind === "ok"
            ? `Backend online · v${health.data.version} · ${health.data.environment}`
            : health.kind === "down"
              ? "Backend offline"
              : "Checking backend…"}
        </button>
      </header>

      {health.kind === "down" && (
        <div className="notice notice--error">
          <strong>The backend is not reachable.</strong> {health.detail} Analysis
          is unavailable until it responds.{" "}
          {IS_LOCAL_DEV ? (
            <>
              Start it with{" "}
              <code>uvicorn src.main:app --reload --port 8000</code>.
            </>
          ) : (
            <>Try again in a moment; if it persists, the deployment needs attention.</>
          )}
        </div>
      )}

      <section className="panel">
        <h2>1 · Choose a paper</h2>

        <div className="picker">
          <input
            ref={inputRef}
            id="file"
            type="file"
            accept={ACCEPTED}
            disabled={busy}
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />
          <label htmlFor="file" className="picker__label">
            {file ? "Choose a different PDF" : "Select a PDF"}
          </label>
          {file && (
            <span className="picker__file">
              {file.name}{" "}
              <span className="muted">({(file.size / 1_048_576).toFixed(2)} MB)</span>
            </span>
          )}
        </div>

        <div className="actions">
          <button
            className="btn btn--primary"
            onClick={() => void run()}
            disabled={!file || busy || health.kind === "down"}
          >
            {busy ? "Analysing…" : "Analyse paper"}
          </button>
          {(file || work.kind === "done") && !busy && (
            <button className="btn" onClick={reset}>
              Clear
            </button>
          )}
        </div>

        {busy && (
          <div className="progress" role="status" aria-live="polite">
            <div className="progress__bar">
              <span />
            </div>
            <p className="progress__text">
              Extracting text, then generating the summary, gap analysis, and
              literature review. This normally takes one to three minutes.
              <br />
              <span className="muted">Elapsed: {elapsed}s</span>
            </p>
          </div>
        )}

        {work.kind === "failed" && (
          <div className="notice notice--error" role="alert">
            <strong>Analysis failed.</strong> {work.error.message}
            <br />
            <span className="muted">{remedyFor(work.error)}</span>
          </div>
        )}
      </section>

      {work.kind === "done" ? (
        <ResultsView data={work.data} />
      ) : (
        <section className="panel panel--muted">
          <h2>2 · Results</h2>
          <p className="muted">
            The summary, research gaps, and literature review will appear here
            once a paper has been analysed.
          </p>
        </section>
      )}

      <footer>
        <p>
          <strong>Scope.</strong> Analysis is grounded in the uploaded paper only.
          Where the paper does not support a section, ResearchForge says so
          rather than inventing content.
        </p>
        <p className="muted">
          Not yet built: multi-paper libraries, saved history, and cross-paper
          literature reviews. Those require the database milestone.
        </p>
      </footer>
    </main>
  );
}
