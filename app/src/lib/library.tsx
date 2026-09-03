"use client";

/**
 * Client state for the research library.
 *
 * Two things live here.
 *
 * `useLibrary` and `usePaper` are thin async hooks over `lib/api.ts`. They
 * exist so no component writes its own fetch-and-setState dance, and so the
 * four states every remote read has (loading, ready, empty, failed) are
 * modelled once instead of being re-invented per page.
 *
 * `SelectionProvider` holds which papers the user has ticked for a cross-paper
 * review. Selection is a transient interface concern, not application data, so
 * it lives in memory. It is shared through context because the choosing
 * happens on Workspace and My Papers while the generating happens on
 * Literature Review.
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
  ApiError,
  getLibraryStats,
  getPaper,
  listPapers,
  type LibraryStats,
  type PaperDetail,
  type PaperListItem,
  type PaperStatus,
  type SortOrder,
} from "@/lib/api";

/* ------------------------------------------------------------------ *
 * Remote read state
 * ------------------------------------------------------------------ */

export type RemoteState<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T }
  /** The library is not connected. Distinct from an empty result. */
  | { kind: "unavailable"; detail: string }
  | { kind: "failed"; error: ApiError };

function toState<T>(error: unknown): RemoteState<T> {
  if (error instanceof ApiError && error.kind === "unavailable") {
    return { kind: "unavailable", detail: error.message };
  }
  return {
    kind: "failed",
    error:
      error instanceof ApiError
        ? error
        : new ApiError("upstream", "Something went wrong. Please try again."),
  };
}

export interface LibraryQuery {
  search: string;
  status: PaperStatus | "all";
  sort: SortOrder;
}

export const DEFAULT_QUERY: LibraryQuery = {
  search: "",
  status: "all",
  sort: "newest",
};

/**
 * The paper list for a given query.
 *
 * Search is debounced so typing does not fire a request per keystroke, and a
 * request counter discards a slow reply that arrives after a newer one, which
 * would otherwise repaint the list with stale results.
 */
export function useLibrary(query: LibraryQuery) {
  const [state, setState] = useState<RemoteState<{ papers: PaperListItem[]; total: number }>>(
    { kind: "loading" },
  );
  const run = useRef(0);

  const load = useCallback(async () => {
    const id = ++run.current;
    setState({ kind: "loading" });
    try {
      const data = await listPapers(query);
      if (run.current === id) setState({ kind: "ready", data });
    } catch (error) {
      if (run.current === id) setState(toState(error));
    }
  }, [query]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), query.search ? 300 : 0);
    return () => clearTimeout(timer);
  }, [load, query.search]);

  return { state, reload: load };
}

/**
 * The most recently SAVED paper, with its stored analysis.
 *
 * Exists to fix a specific bug on the dashboard. "Recent analysis" used to
 * read only from the in-memory session, which is cleared on reload, so a
 * returning user saw "No analysis yet" printed directly beneath a stat card
 * reading "Saved papers: 2". The empty state was contradicted by the number
 * above it - and the number was the true one.
 *
 * Loads the newest paper and then its detail, because the list endpoint
 * returns metadata while the dashboard needs the analysis body.
 */
export function useMostRecentPaper() {
  const [state, setState] = useState<RemoteState<PaperDetail | null>>({ kind: "loading" });
  const run = useRef(0);

  const load = useCallback(async () => {
    const id = ++run.current;
    try {
      const list = await listPapers({ sort: "newest", limit: 1 });
      if (run.current !== id) return;
      const newest = list.papers[0];
      if (!newest) {
        // A genuinely empty library. `null` is the honest answer and is
        // distinct from "we could not look", which lands in the catch below.
        setState({ kind: "ready", data: null });
        return;
      }
      const detail = await getPaper(newest.id);
      if (run.current === id) setState({ kind: "ready", data: detail });
    } catch (error) {
      if (run.current === id) setState(toState(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, reload: load };
}

/** One paper with its stored analysis. */
export function usePaper(id: string | null) {
  const [state, setState] = useState<RemoteState<PaperDetail>>({ kind: "loading" });

  const load = useCallback(async () => {
    if (!id) return;
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", data: await getPaper(id) });
    } catch (error) {
      setState(toState(error));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, reload: load };
}

/** Dashboard counts. Real rows only; there is no fallback to zeros. */
export function useLibraryStats() {
  const [state, setState] = useState<RemoteState<LibraryStats>>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      setState({ kind: "ready", data: await getLibraryStats() });
    } catch (error) {
      setState(toState(error));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { state, reload: load };
}

/* ------------------------------------------------------------------ *
 * Cross-paper selection
 * ------------------------------------------------------------------ */

interface SelectionValue {
  selected: PaperListItem[];
  ids: string[];
  isSelected: (id: string) => boolean;
  toggle: (paper: PaperListItem) => void;
  remove: (id: string) => void;
  clear: () => void;
  /** The backend requires at least two papers for a cross-paper review. */
  canReview: boolean;
}

const SelectionContext = createContext<SelectionValue | null>(null);

export function SelectionProvider({ children }: { children: React.ReactNode }) {
  const [selected, setSelected] = useState<PaperListItem[]>([]);

  const toggle = useCallback((paper: PaperListItem) => {
    setSelected((prev) =>
      prev.some((p) => p.id === paper.id)
        ? prev.filter((p) => p.id !== paper.id)
        : [...prev, paper],
    );
  }, []);

  const remove = useCallback((id: string) => {
    setSelected((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clear = useCallback(() => setSelected([]), []);

  const value = useMemo<SelectionValue>(() => {
    const ids = selected.map((p) => p.id);
    return {
      selected,
      ids,
      isSelected: (id: string) => ids.includes(id),
      toggle,
      remove,
      clear,
      canReview: selected.length >= 2,
    };
  }, [selected, toggle, remove, clear]);

  return (
    <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>
  );
}

export function useSelection(): SelectionValue {
  const ctx = useContext(SelectionContext);
  if (!ctx) throw new Error("useSelection must be used inside <SelectionProvider>.");
  return ctx;
}

/* ------------------------------------------------------------------ *
 * Formatting shared by the library views
 * ------------------------------------------------------------------ */

export function formatSize(bytes: number | null | undefined): string {
  if (bytes == null) return "Unknown size";
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return date.toLocaleDateString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
