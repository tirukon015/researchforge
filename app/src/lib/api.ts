/**
 * Typed client for the ResearchForge backend.
 *
 * All network access lives here so the components stay presentational and the
 * error vocabulary is defined in exactly one place.
 *
 * The base URL comes from the environment and is never hard-coded. NEXT_PUBLIC_
 * values are inlined into the browser bundle at build time, so this must only
 * ever hold a public, non-secret value.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
 */
export type ApiErrorKind =
  | "offline"
  | "rejected"
  | "upstream"
  | "config"
  | "malformed";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;

  constructor(kind: ApiErrorKind, message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
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
      `Could not reach the backend at ${API_BASE_URL}. It may be offline, or the request may have been blocked by CORS.`,
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
