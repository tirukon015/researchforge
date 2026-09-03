"use client";

/**
 * The current working session, shared across routes.
 *
 * WHY THIS EXISTS
 * ---------------
 * The analysis workspace lives on the dashboard, but the Literature Review
 * page shows a section of the same result. Without a shared holder, navigating
 * between them would throw the analysis away and the user would have to spend
 * another three model calls to read a tab.
 *
 * WHY IT IS DELIBERATELY NOT PERSISTED
 * ------------------------------------
 * This is in-memory only: a reload clears it, exactly as a stateless backend
 * implies. Writing it to localStorage would make "My Papers" look like a
 * library while the database milestone is still unbuilt - a persistence
 * illusion that breaks the moment the user opens another browser. Empty
 * states say what is actually true instead. When the database lands, this
 * provider is the seam that gets a real data source behind it.
 *
 * Nothing here fabricates data. Every number the dashboard shows is derived
 * from analyses this session actually ran.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  analyzePaper,
  ApiError,
  checkHealth,
  type AnalysisResponse,
  type HealthPayload,
} from "@/lib/api";

/** One completed analysis, plus what we know about the file it came from. */
export interface AnalysisRecord {
  /** Stable id so lists can key on it without using an array index. */
  id: string;
  filename: string;
  sizeBytes: number;
  completedAt: Date;
  data: AnalysisResponse;
}

export type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthPayload }
  | { kind: "down"; detail: string };

export type WorkState =
  | { kind: "idle" }
  | { kind: "working" }
  | { kind: "done" }
  | { kind: "failed"; error: ApiError };

interface SessionValue {
  health: HealthState;
  refreshHealth: () => void;

  /** The file staged for analysis, if any. */
  file: File | null;
  setFile: (file: File | null) => void;

  work: WorkState;
  /** Seconds since the running analysis started; 0 when idle. */
  elapsed: number;

  /** Analyses completed in this browser session, newest first. */
  records: AnalysisRecord[];
  /** The one currently open in the workspace. */
  current: AnalysisRecord | null;
  selectRecord: (id: string) => void;

  analyse: () => Promise<void>;
  clearStaged: () => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });
  const [file, setFileState] = useState<File | null>(null);
  const [work, setWork] = useState<WorkState>({ kind: "idle" });
  const [elapsed, setElapsed] = useState(0);
  const [records, setRecords] = useState<AnalysisRecord[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);

  // Guards a state update after unmount, and lets a stale in-flight health
  // check lose to a newer one.
  const healthRun = useRef(0);

  const refreshHealth = useCallback(() => {
    const run = ++healthRun.current;
    setHealth({ kind: "loading" });
    void checkHealth()
      .then((data) => {
        if (healthRun.current === run) setHealth({ kind: "ok", data });
      })
      .catch((error: unknown) => {
        if (healthRun.current !== run) return;
        setHealth({
          kind: "down",
          detail:
            error instanceof ApiError ? error.message : "Backend unreachable.",
        });
      });
  }, []);

  useEffect(() => {
    refreshHealth();
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

  const setFile = useCallback((selected: File | null) => {
    setFileState(selected);
    // Drop a previous failure so the screen never shows one paper's error
    // beside another paper's filename. A completed record is kept - it is a
    // real result, and the user may still be reading it.
    setWork((w) => (w.kind === "failed" ? { kind: "idle" } : w));
  }, []);

  const clearStaged = useCallback(() => {
    setFileState(null);
    setWork({ kind: "idle" });
  }, []);

  // Guards against a second analysis being launched while one is in flight.
  //
  // A ref, not state, because only a ref is updated synchronously. Two clicks
  // landing in the same React batch would both read the OLD value of a state
  // flag and both proceed; each analysis costs three model calls against a
  // rate-limited quota, so the duplicate is expensive as well as pointless.
  // The button also unmounts while `work.kind === "working"`, but that is a
  // rendering consequence and cannot be relied on to have happened yet.
  const inFlight = useRef(false);

  const analyse = useCallback(async () => {
    if (!file || inFlight.current) return;
    inFlight.current = true;
    const staged = file;
    setWork({ kind: "working" });
    try {
      const data = await analyzePaper(staged);
      const record: AnalysisRecord = {
        id:
          typeof crypto !== "undefined" && "randomUUID" in crypto
            ? crypto.randomUUID()
            : `${Date.now()}-${staged.name}`,
        filename: data.document.filename || staged.name,
        sizeBytes: staged.size,
        completedAt: new Date(),
        data,
      };
      setRecords((prev) => [record, ...prev]);
      setCurrentId(record.id);
      setWork({ kind: "done" });
      setFileState(null);
    } catch (error) {
      // The staged file is deliberately NOT cleared here. A failed analysis
      // must leave the paper ready to try again, especially a rate limit,
      // where the fix is to wait rather than to upload the file a second time.
      setWork({
        kind: "failed",
        error:
          error instanceof ApiError
            ? error
            : new ApiError("upstream", "An unexpected error occurred."),
      });
    } finally {
      // In a `finally` so a thrown error cannot leave the guard stuck on and
      // the button permanently dead.
      inFlight.current = false;
    }
  }, [file]);

  const selectRecord = useCallback((id: string) => setCurrentId(id), []);

  const current = useMemo(
    () => records.find((r) => r.id === currentId) ?? records[0] ?? null,
    [records, currentId],
  );

  const value = useMemo<SessionValue>(
    () => ({
      health,
      refreshHealth,
      file,
      setFile,
      work,
      elapsed,
      records,
      current,
      selectRecord,
      analyse,
      clearStaged,
    }),
    [
      health,
      refreshHealth,
      file,
      setFile,
      work,
      elapsed,
      records,
      current,
      selectRecord,
      analyse,
      clearStaged,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used inside <SessionProvider>.");
  }
  return ctx;
}

/* ------------------------------------------------------------------ *
 * Derived figures
 * ------------------------------------------------------------------ */

/**
 * Counts for the dashboard, all derived from real completed analyses.
 *
 * `gapsFound` counts only gaps the backend actually identified: a result the
 * model marked as having insufficient evidence contributes zero, never a
 * consolation number.
 */
export function sessionStats(records: AnalysisRecord[]) {
  let gapsFound = 0;
  let reviews = 0;

  for (const record of records) {
    const gaps = record.data.research_gaps;
    if (!gaps.insufficient_evidence) gapsFound += gaps.identified_gaps.length;
    if (!record.data.literature_review.insufficient_evidence) reviews += 1;
  }

  return { papersAnalysed: records.length, gapsFound, reviews };
}
