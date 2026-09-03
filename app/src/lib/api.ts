/**
 * Typed client for the ResearchForge backend.
 *
 * All network access lives here so the components stay presentational and the
 * error vocabulary is defined in exactly one place.
 *
 * WHERE THE BASE URL COMES FROM
 * -----------------------------
 * In production the frontend and the backend are one deployment: vercel.json
 * rewrites /health and /api/* to the FastAPI service, so the API is reachable
 * on whatever origin the page was served from. The base URL is therefore the
 * EMPTY STRING, which makes every call a same-origin relative path.
 *
 * That matters beyond tidiness. Pinning the base to one absolute host makes
 * every OTHER host a cross-origin caller, and the browser then blocks the page
 * unless FastAPI's CORS allowlist happens to name it - which is exactly how a
 * working *.vercel.app URL and a broken custom domain arise from one build.
 * A relative path is correct on every domain the project will ever have.
 *
 * Local development is the one case where the two really are separate origins
 * (Next on :3000, uvicorn on :8000), so that - and only that - defaults to
 * localhost.
 *
 * NEXT_PUBLIC_API_BASE_URL still overrides both, for the genuinely separate
 * deployment. NEXT_PUBLIC_ values are inlined into the browser bundle at build
 * time, so it must only ever hold a public, non-secret value.
 */

const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

export const API_BASE_URL =
  configuredBaseUrl !== undefined && configuredBaseUrl !== ""
    ? // Trailing slashes would produce `//health`, which some hosts 404.
      configuredBaseUrl.replace(/\/+$/, "")
    : process.env.NODE_ENV === "development"
      ? "http://localhost:8000"
      : "";

/** How to name the backend's location in UI text and error messages. */
export const API_BASE_LABEL = API_BASE_URL || "this site (same origin)";

/* ------------------------------------------------------------------ *
 * Response types - these mirror src/schemas/analysis.py exactly.
 * ------------------------------------------------------------------ */

export interface ResearchGap {
  gap: string;
  why_it_matters: string;
  evidence: string;
}

export interface Summary {
  research_problem: string;
  methodology: string;
  key_findings: string[];
  conclusion: string;
  insufficient_evidence: string[];
}

export interface ResearchGaps {
  stated_limitations: string[];
  identified_gaps: ResearchGap[];
  insufficient_evidence: boolean;
  evidence_note: string;
}

export interface LiteratureReview {
  scope_note: string;
  major_themes: string[];
  relevant_findings: string[];
  comparisons: string[];
  research_trends: string[];
  limitations: string[];
  future_directions: string[];
  insufficient_evidence: boolean;
}

export interface DocumentInfo {
  filename: string;
  page_count: number;
  extracted_characters: number;
  chunk_count: number;
  truncated: boolean;
}

export interface AnalysisResponse {
  document: DocumentInfo;
  summary: Summary;
  research_gaps: ResearchGaps;
  literature_review: LiteratureReview;
  model_used: string;
}

export interface HealthPayload {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  /** Whether durable storage is configured on the server. */
  library?: boolean;
}

/* ------------------------------------------------------------------ *
 * Errors
 * ------------------------------------------------------------------ */

/**
 * `kind` lets the UI choose its wording without string-matching messages.
 *
 *   offline   - the backend could not be reached at all (or CORS blocked us)
 *   rejected  - the upload was refused (bad PDF, too large): the user can fix it
 *   upstream  - the AI service failed or returned something unusable
 *   config    - the server has no API key: an operator must fix it
 *   malformed - we got a 200 whose body was not the shape we expect
 *   ratelimited - the AI provider refused on quota (429), not a fault
 *   unavailable - the research library is not connected (503)
 *   notfound  - the record does not exist (404)
 *   conflict  - the write would destroy something (409)
 */
export type ApiErrorKind =
  | "offline"
  | "rejected"
  | "upstream"
  | "config"
  | "malformed"
  // Kept apart from "upstream" on purpose. A rate limit means the service is
  // working and we are over an allowance, which needs different words and a
  // different suggestion than "the AI service is broken".
  | "ratelimited"
  // Library-specific. "unavailable" means there is no database configured,
  // which must never be shown as "you have no papers".
  | "unavailable"
  | "notfound"
  | "conflict";

/** Extra facts a rate limit carries. Both are optional because the provider
 *  does not always supply them, and a missing value must stay missing rather
 *  than being filled in with a guess the UI would then count down from. */
export interface ApiErrorDetails {
  status?: number;
  /** Seconds the provider asked us to wait, when it said. */
  retryAfterSeconds?: number;
  /** True only when the server saw positive evidence of a spent allowance. */
  quotaExhausted?: boolean;
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly retryAfterSeconds?: number;
  readonly quotaExhausted?: boolean;

  constructor(kind: ApiErrorKind, message: string, details?: number | ApiErrorDetails) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    const d = typeof details === "number" ? { status: details } : (details ?? {});
    this.status = d.status;
    this.retryAfterSeconds = d.retryAfterSeconds;
    this.quotaExhausted = d.quotaExhausted;
  }
}

/**
 * Read the rate-limit facts the backend put on the response.
 *
 * `Retry-After` and `X-Quota-Exhausted` are set by src/api/analyze.py, and
 * only when the provider genuinely reported them - so an absent header means
 * "not known", and this returns undefined rather than inventing a default.
 * Both are listed in the backend's CORS expose_headers; without that they read
 * as null in local development, which is handled here as "not known" too.
 */
function readRateLimit(res: Response): ApiErrorDetails {
  const raw = res.headers.get("Retry-After");
  const seconds = raw === null ? NaN : Number(raw);
  return {
    status: res.status,
    retryAfterSeconds: Number.isFinite(seconds) && seconds > 0 ? seconds : undefined,
    quotaExhausted: res.headers.get("X-Quota-Exhausted") === "true",
  };
}

/** Pull FastAPI's `detail` out of an error body, whatever shape it arrived in. */
async function readDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    // FastAPI validation errors arrive as a list of objects.
    if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      return String(body.detail[0].msg);
    }
  } catch {
    /* body was not JSON - fall through */
  }
  return fallback;
}

/** Minimal runtime check that a 200 body really is an AnalysisResponse. */
function isAnalysisResponse(value: unknown): value is AnalysisResponse {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.document === "object" &&
    v.document !== null &&
    typeof v.summary === "object" &&
    v.summary !== null &&
    typeof v.research_gaps === "object" &&
    v.research_gaps !== null &&
    typeof v.literature_review === "object" &&
    v.literature_review !== null
  );
}

/* ------------------------------------------------------------------ *
 * Calls
 * ------------------------------------------------------------------ */

export async function checkHealth(
  signal?: AbortSignal,
): Promise<HealthPayload> {
  const res = await fetch(`${API_BASE_URL}/health`, {
    signal: signal ?? AbortSignal.timeout(10_000),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError("offline", `Backend responded with HTTP ${res.status}.`, res.status);
  }
  return (await res.json()) as HealthPayload;
}

/**
 * Upload a PDF and get the analysis back.
 *
 * The timeout is generous: a long paper legitimately takes minutes, because the
 * backend makes three separate reasoning calls (and more for a chunked paper).
 */
export async function analyzePaper(
  file: File,
  { timeoutMs = 600_000 }: { timeoutMs?: number } = {},
): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("file", file);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    // A CORS rejection, a dead server, and a DNS failure all surface as a
    // generic TypeError, so the message names the possibilities rather than
    // pretending to know which one happened.
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new ApiError(
        "offline",
        "The analysis took longer than expected and the request timed out. Very long papers can exceed the limit - try a shorter document.",
      );
    }
    throw new ApiError(
      "offline",
      `Could not reach the backend at ${API_BASE_LABEL}. It may be offline, or the request may have been blocked by CORS.`,
    );
  }

  if (!res.ok) {
    const detail = await readDetail(res, `The server returned HTTP ${res.status}.`);
    if (res.status === 413 || res.status === 422 || res.status === 415) {
      throw new ApiError("rejected", detail, res.status);
    }
    if (res.status === 503) {
      throw new ApiError("config", detail, res.status);
    }
    // Before the 5xx branch: 429 is not a server fault and must not be
    // reported as one. Retrying it the way "upstream" invites spends more of
    // the allowance that just ran out.
    if (res.status === 429) {
      throw new ApiError("ratelimited", detail, readRateLimit(res));
    }
    if (res.status === 502 || res.status >= 500) {
      throw new ApiError("upstream", detail, res.status);
    }
    throw new ApiError("rejected", detail, res.status);
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new ApiError("malformed", "The server returned a response that was not valid JSON.");
  }
  if (!isAnalysisResponse(body)) {
    throw new ApiError(
      "malformed",
      "The server returned a response in an unexpected shape. The frontend and backend versions may not match.",
    );
  }
  return body;
}

/* ------------------------------------------------------------------ *
 * Research library
 * ------------------------------------------------------------------ *
 * These mirror src/schemas/library.py. The library is optional: a
 * deployment with no database answers 503, which surfaces here as an
 * ApiError of kind "unavailable" so the interface can say "not connected"
 * rather than "you have no papers". Those are different claims.
 */

export type PaperStatus = "processing" | "ready" | "failed";
export type SortOrder = "newest" | "oldest" | "title";

export interface PaperListItem {
  id: string;
  title: string;
  filename: string;
  status: PaperStatus;
  page_count: number | null;
  file_size_bytes: number | null;
  created_at: string;
  updated_at: string;
  has_analysis: boolean;
  gap_count: number | null;
}

export interface PaperListResponse {
  papers: PaperListItem[];
  total: number;
}

export interface PaperDetail {
  id: string;
  title: string;
  filename: string;
  status: PaperStatus;
  page_count: number | null;
  extracted_characters: number | null;
  file_size_bytes: number | null;
  content_type: string | null;
  created_at: string;
  updated_at: string;
  summary: Summary | null;
  research_gaps: ResearchGaps | null;
  literature_review: LiteratureReview | null;
  model_used: string | null;
  chunk_count: number | null;
  truncated: boolean | null;
}

export interface ReviewPaperRef {
  id: string;
  title: string;
  filename: string;
}

export interface ReviewRecord {
  id: string;
  title: string;
  model_used: string;
  content: LiteratureReview;
  paper_count: number;
  papers: ReviewPaperRef[];
  created_at: string;
}

export interface ReviewListResponse {
  reviews: ReviewRecord[];
  total: number;
}

export interface LibraryStats {
  papers_analysed: number;
  research_gaps_found: number;
  literature_reviews: number;
  saved_papers: number;
}

export interface SavePaperInput {
  title: string;
  filename: string;
  file_size_bytes?: number | null;
  content_type?: string | null;
  document: DocumentInfo;
  summary: Summary;
  research_gaps: ResearchGaps;
  literature_review: LiteratureReview;
  model_used: string;
}

/** One place that turns any library response into a value or an ApiError. */
async function libraryRequest<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = 30_000, ...rest } = init ?? {};
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      signal: AbortSignal.timeout(timeoutMs),
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new ApiError("offline", "The request took too long. Please try again.");
    }
    throw new ApiError("offline", "Could not reach the server. Check your connection.");
  }

  if (!res.ok) {
    const detail = await readDetail(res, `The server returned HTTP ${res.status}.`);
    if (res.status === 503) throw new ApiError("unavailable", detail, res.status);
    if (res.status === 404) throw new ApiError("notfound", detail, res.status);
    if (res.status === 409) throw new ApiError("conflict", detail, res.status);
    // A cross-paper review is a generation call and can be rate limited like
    // any other, so this path needs the same distinction the upload path has.
    if (res.status === 429) throw new ApiError("ratelimited", detail, readRateLimit(res));
    if (res.status === 422 || res.status === 413) {
      throw new ApiError("rejected", detail, res.status);
    }
    if (res.status >= 500) throw new ApiError("upstream", detail, res.status);
    throw new ApiError("rejected", detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError("malformed", "The server returned a response that was not valid JSON.");
  }
}

export function savePaper(input: SavePaperInput): Promise<PaperDetail> {
  return libraryRequest<PaperDetail>("/api/papers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function listPapers(options: {
  search?: string;
  status?: PaperStatus | "all";
  sort?: SortOrder;
  limit?: number;
  offset?: number;
} = {}): Promise<PaperListResponse> {
  const params = new URLSearchParams();
  if (options.search?.trim()) params.set("search", options.search.trim());
  if (options.status && options.status !== "all") params.set("status", options.status);
  if (options.sort) params.set("sort", options.sort);
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  const query = params.toString();
  return libraryRequest<PaperListResponse>(`/api/papers${query ? `?${query}` : ""}`);
}

export function getPaper(id: string): Promise<PaperDetail> {
  return libraryRequest<PaperDetail>(`/api/papers/${encodeURIComponent(id)}`);
}

export function deletePaper(id: string): Promise<{ id: string; deleted: boolean }> {
  return libraryRequest(`/api/papers/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function getLibraryStats(): Promise<LibraryStats> {
  return libraryRequest<LibraryStats>("/api/papers/stats");
}

/**
 * Generate a review across several saved papers.
 *
 * The timeout is generous for the same reason `analyzePaper`'s is: this is a
 * reasoning call over several papers and legitimately takes minutes.
 */
export function createCrossReview(
  paperIds: string[],
  title?: string,
): Promise<ReviewRecord> {
  return libraryRequest<ReviewRecord>("/api/reviews/cross", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paper_ids: paperIds, ...(title ? { title } : {}) }),
    timeoutMs: 600_000,
  });
}

export function listReviews(): Promise<ReviewListResponse> {
  return libraryRequest<ReviewListResponse>("/api/reviews");
}

export function deleteReview(id: string): Promise<{ id: string; deleted: boolean }> {
  return libraryRequest(`/api/reviews/${encodeURIComponent(id)}`, { method: "DELETE" });
}
