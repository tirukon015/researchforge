# ruff: noqa: E501  (diagram labels and alt text are long literal strings by design)
"""Build the case-study diagrams as SVG, then render each to PNG.

    python docs/screenshots/case-study/diagrams/build_diagrams.py

Every box in these diagrams corresponds to code in this repository at the
commit named in FOOTER. Nothing is drawn that the code does not do:

    solid blue    CURRENT   implemented and on the production path
    solid violet  EXTERNAL  a third-party service the code calls
    dashed grey   PLANNED   scaffolding or design only; nothing calls it
    dotted grey   RETIRED   kept for history; nothing routes to it

PNG rendering uses headless Chrome (already a requirement of
docs/report/render_diagrams.py). The SVG files are the source of truth; the
PNGs are regenerated from them.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
from html import escape

HERE = pathlib.Path(__file__).resolve().parent
FOOTER = "Verified against the ResearchForge repository at commit 33bc740 (2026-09-06). Diagram built 2026-09-25."

FONT = "Segoe UI, Inter, Arial, sans-serif"
MONO = "Consolas, 'Cascadia Mono', monospace"

STYLE = {
    "current": dict(fill="#eff6ff", stroke="#2563eb", title="#1e3a8a", text="#1e293b", dash=""),
    "external": dict(fill="#f5f3ff", stroke="#7c3aed", title="#4c1d95", text="#1e293b", dash=""),
    "planned": dict(fill="#f8fafc", stroke="#94a3b8", title="#475569", text="#64748b", dash="8 6"),
    "retired": dict(fill="#f8fafc", stroke="#cbd5e1", title="#94a3b8", text="#94a3b8", dash="2 5"),
    "neutral": dict(fill="#ffffff", stroke="#cbd5e1", title="#0f172a", text="#334155", dash=""),
    "decision": dict(fill="#fffbeb", stroke="#d97706", title="#78350f", text="#78350f", dash=""),
    "error": dict(fill="#fef2f2", stroke="#dc2626", title="#7f1d1d", text="#7f1d1d", dash=""),
}


class Svg:
    def __init__(self, w: int, h: int, title: str, subtitle: str) -> None:
        self.w, self.h = w, h
        self.parts: list[str] = []
        self.text(40, 52, title, size=30, weight=700, fill="#0f172a")
        self.text(40, 82, subtitle, size=16, fill="#475569")

    def text(self, x, y, s, size=15, weight=400, fill="#1e293b", anchor="start", mono=False, italic=False):
        fam = MONO if mono else FONT
        style = "font-style:italic;" if italic else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" style="{style}">{escape(s)}</text>'
        )

    def box(self, x, y, w, h, title, lines=(), kind="current", tag=None, center=False, title_size=17):
        st = STYLE[kind]
        dash = f' stroke-dasharray="{st["dash"]}"' if st["dash"] else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{st["fill"]}" '
            f'stroke="{st["stroke"]}" stroke-width="2"{dash}/>'
        )
        tx = x + w / 2 if center else x + 16
        anchor = "middle" if center else "start"
        self.text(tx, y + 28, title, size=title_size, weight=700, fill=st["title"], anchor=anchor)
        if tag:
            self.tag(x + w - 12, y + 12, tag, kind)
        for i, line in enumerate(lines):
            mono = line.startswith("`")
            self.text(tx, y + 54 + i * 21, line.strip("`"), size=14, fill=st["text"], anchor=anchor, mono=mono)

    def tag(self, right, top, label, kind):
        st = STYLE[kind]
        width = 9 * len(label) + 18
        self.parts.append(
            f'<rect x="{right - width}" y="{top}" width="{width}" height="22" rx="11" fill="#ffffff" '
            f'stroke="{st["stroke"]}" stroke-width="1.5"/>'
        )
        self.text(right - width / 2, top + 16, label, size=11, weight=700, fill=st["title"], anchor="middle")

    def container(self, x, y, w, h, label):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#f8fafc" stroke="#94a3b8" '
            f'stroke-width="1.5"/>'
        )
        self.text(x + 20, y + 30, label, size=15, weight=700, fill="#334155")

    def arrow(self, pts, label=None, label_at=None, dashed=False, color="#475569", anchor="middle"):
        d = "M " + " L ".join(f"{px} {py}" for px, py in pts)
        dash = ' stroke-dasharray="7 6"' if dashed else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#arrow)"/>'
        )
        if label:
            lx, ly = label_at or ((pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2 - 8)
            for i, part in enumerate(label.split("\n")):
                self.parts.append(
                    f'<text x="{lx}" y="{ly + i * 17}" font-family="{FONT}" font-size="13" fill="#334155" '
                    f'text-anchor="{anchor}" paint-order="stroke" stroke="#ffffff" stroke-width="5">{escape(part)}</text>'
                )

    def legend(self, x, y, kinds):
        labels = {
            "current": "Current: implemented",
            "external": "External service",
            "planned": "Planned: nothing calls it",
            "retired": "Retired: history only",
            "decision": "Decision point",
            "error": "Rejected / error outcome",
        }
        for i, k in enumerate(kinds):
            st = STYLE[k]
            dash = f' stroke-dasharray="{st["dash"]}"' if st["dash"] else ""
            yy = y + i * 28
            self.parts.append(
                f'<rect x="{x}" y="{yy}" width="34" height="20" rx="5" fill="{st["fill"]}" stroke="{st["stroke"]}" stroke-width="2"{dash}/>'
            )
            self.text(x + 46, yy + 15, labels[k], size=14, fill="#334155")

    def render(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}">'
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
            'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#475569"/></marker></defs>'
            f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>'
        )
        foot = (
            f'<text x="40" y="{self.h - 22}" font-family="{FONT}" font-size="12" fill="#94a3b8">{escape(FOOTER)}</text>'
        )
        return head + "".join(self.parts) + foot + "</svg>"


# ---------------------------------------------------------------------------
# 1. System architecture
# ---------------------------------------------------------------------------
def architecture() -> Svg:
    s = Svg(1600, 1080, "ResearchForge: system architecture",
            "One Vercel project, two services behind one origin. Data access runs as the signed-in user, so Postgres RLS decides what exists.")
    s.box(600, 110, 400, 84, "Browser", ["Next.js client  ·  supabase-js (sign-in only)"], "neutral", center=True)

    s.container(60, 240, 1480, 430, "Vercel project \"researchforge\"  ·  researchforge.rukon.dev  ·  one origin")
    s.box(90, 285, 1420, 60, "vercel.json rewrites  ·  /api/* and /health -> backend service  ·  every other path -> frontend service",
          [], "neutral", title_size=15)
    s.box(90, 370, 600, 280, "Next.js 16 frontend  (app/)", [
        "React 19 · TypeScript strict · plain CSS",
        "/                     public landing page",
        "/sign-in  /sign-up  /forgot-password  /reset-password",
        "/auth/callback        Google OAuth (PKCE)",
        "/dashboard            upload + analysis",
        "/papers  /papers/[id] private library",
        "/literature-review    cross-paper review",
        "/workspace  /settings (account, owner AI config)",
        "AuthGate: UX redirect only, not the security boundary",
    ], "current", tag="CURRENT")
    s.box(760, 370, 750, 280, "FastAPI backend  (src/)  ·  Python  ·  maxDuration 300 s", [
        "POST /api/analyze        PDF -> validate -> extract -> cache -> 3 model passes",
        "/api/papers              save · list · stats · open · delete",
        "/api/reviews             cross-paper literature review (from stored analyses)",
        "/api/owner               status, AI provider choice + availability",
        "GET /health              library: bool, auth: bool (no URLs, no keys)",
        "require_user             token checked with Supabase /auth/v1/user, 5 s cache",
        "RoutedLLMProvider        owner's primary + at most one fallback",
        "pypdf ingestion · Pydantic schemas · versioned prompts",
    ], "current", tag="CURRENT")
    s.arrow([(690, 510), (756, 510)], "Bearer token\nrelative /api path", label_at=(723, 480))
    s.arrow([(800, 194), (800, 281)], "HTTPS", label_at=(812, 222), anchor="start")

    y = 730
    s.box(60, y, 330, 130, "Supabase Auth", ["email + password", "Google sign-in (PKCE)", "issues the user's access token"], "external", tag="EXTERNAL")
    s.box(420, y, 400, 130, "Supabase Postgres", ["papers · analyses · literature_reviews", "analysis_cache · system_settings · app_owners",
                                                  "Row Level Security: user_id = auth.uid()"], "external", tag="EXTERNAL")
    s.box(850, y, 330, 130, "Anthropic API", ["Claude", "`default model: claude-opus-5", "one of the two routed providers"], "external", tag="EXTERNAL")
    s.box(1210, y, 330, 130, "Groq API", ["OpenAI-compatible endpoint", "`default model: qwen/qwen3.6-27b", "one of the two routed providers"], "external", tag="EXTERNAL")

    s.arrow([(600, 150), (30, 150), (30, 795), (56, 795)], "sign in, refresh session", label_at=(320, 140))
    s.arrow([(900, 650), (900, 690), (330, 690), (330, 726)], "verify token", label_at=(470, 684))
    s.arrow([(1000, 650), (1000, 700), (620, 700), (620, 726)], "anon key + user JWT  ->  RLS applies", label_at=(760, 718))
    s.arrow([(1100, 650), (1015, 726)])
    s.arrow([(1300, 650), (1375, 726)])
    s.text(1195, 700, "generate_structured / generate_text", size=13, fill="#334155", anchor="middle")

    y2 = 900
    s.box(60, y2, 420, 110, "Jina embeddings v3 (1024-d)", ["provider interface + request body written, tested offline",
                                                           "HTTP call deliberately not implemented"], "planned", tag="PLANNED")
    s.box(510, y2, 420, 110, "pgvector chunks table / retrieval", ["table + RLS policy exist in migrations",
                                                                   "nothing writes or queries it: no RAG"], "planned", tag="PLANNED")
    s.box(960, y2, 280, 110, "Google Gemini", ["provider module kept for", "historical rows; not routed"], "retired", tag="RETIRED")
    s.legend(1270, y2 + 4, ["current", "external", "planned", "retired"])
    return s


# ---------------------------------------------------------------------------
# 2. User workflow
# ---------------------------------------------------------------------------
def workflow() -> Svg:
    s = Svg(1600, 1000, "ResearchForge: the verified user workflow",
            "Traced from the Next.js routes and API calls. Each step names the screen and endpoint that implement it.")
    steps = [
        ("1  Sign in", ["/sign-in or Google", "Supabase Auth session"]),
        ("2  Upload a PDF", ["/dashboard drop zone", "type, empty, 25 MB checks"]),
        ("3  Analyse", ["POST /api/analyze", "1 to 3 minutes typical"]),
        ("4  Read the result", ["tabs: Summary · Gaps ·", "Literature Review · Paper info"]),
        ("5  Save to library", ["POST /api/papers", "analysis passed back, not re-run"]),
    ]
    x, y, w, h, gap = 40, 140, 280, 118, 25
    for i, (t, lines) in enumerate(steps):
        bx = x + i * (w + gap)
        s.box(bx, y, w, h, t, lines, "current")
        if i < len(steps) - 1:
            s.arrow([(bx + w, y + h / 2), (bx + w + gap - 2, y + h / 2)])

    # Outcomes of step 3, directly beneath it.
    ax = x + 2 * (w + gap)  # left edge of "Analyse"
    oy = 330
    s.box(ax - 330, oy, 310, 104, "Rejected upload", ["422 not a PDF, scanned, encrypted", "413 over 25 MB"], "error")
    s.box(ax - 5, oy, 290, 104, "Same text seen before", ["content-hash cache hit", "stored result, 0 model calls"], "decision")
    s.box(ax + 300, oy, 330, 104, "Provider problem", ["429 rate limit (Retry-After)", "502 unusable reply · 503 no key"], "error")
    s.arrow([(ax + 50, y + h), (ax - 175, oy - 4)], dashed=True)
    s.arrow([(ax + 140, y + h), (ax + 140, oy - 4)], dashed=True)
    s.arrow([(ax + 230, y + h), (ax + 465, oy - 4)], dashed=True)

    steps2 = [
        ("6  My Papers", ["/papers: search, filter,", "sort, open, delete"]),
        ("7  Select 2 or more", ["papers with stored analyses", "checkbox selection"]),
        ("8  Cross-paper review", ["POST /api/reviews/cross", "one model call"]),
        ("9  Read + copy", ["/literature-review", "copy buttons; no file export"]),
    ]
    y2 = 560
    for i, (t, lines) in enumerate(steps2):
        bx = x + 150 + i * (w + gap + 20)
        s.box(bx, y2, w, h, t, lines, "current")
        if i < len(steps2) - 1:
            s.arrow([(bx + w, y2 + h / 2), (bx + w + gap + 18, y2 + h / 2)])
    s5 = x + 4 * (w + gap) + w / 2
    s.arrow([(s5, y + h), (s5, 500), (x + 150 + w / 2, 500), (x + 150 + w / 2, y2 - 4)], "saved papers accumulate",
            label_at=(900, 492))

    s.box(1180, 740, 380, 150, "Owner only: Settings  ->  AI", ["choose primary: Claude or Groq Qwen 3.6 27B",
                                                               "the other becomes the automatic fallback",
                                                               "switch a provider off entirely",
                                                               "enforced by the API and by RLS"], "current")
    s.legend(40, 750, ["current", "decision", "error"])
    s.text(40, 870, "Not in the product: search inside papers, notes, tags or folders, citation export,", size=14, fill="#64748b")
    s.text(40, 892, "collaboration or sharing, OCR. The literature review covers the prior work the papers themselves discuss.", size=14, fill="#64748b")
    return s


# ---------------------------------------------------------------------------
# 3. Data / knowledge flow
# ---------------------------------------------------------------------------
def data_flow() -> Svg:
    s = Svg(1600, 1270, "ResearchForge: data flow through one analysis",
            "Whole-document grounded generation. No embeddings, no vector search, no retrieval step: this is not RAG.")
    L, LW = 40, 520
    s.box(L, 120, LW, 76, "PDF bytes (multipart upload)", ["read once; size checked on the real byte count"], "neutral")
    s.box(L, 226, LW, 100, "Validate  (src/ingestion/pdf.py)", ["%PDF signature · empty-password decrypt attempt",
                                                                "near-empty text layer -> rejected as scanned (422)"], "current")
    s.box(L, 356, LW, 100, "Extract + clean  (pypdf)", ["ligatures normalised · hyphenated breaks rejoined",
                                                        "spaces collapsed, newlines kept · nothing removed"], "current")
    s.box(L, 486, LW, 80, "Content hash  (SHA-256 of cleaned text)", ["+ ANALYSIS_VERSION  ->  analysis_cache lookup"], "current")
    s.box(L, 606, LW, 120, "Fits in context?  (400,000 characters)", ["yes: whole paper is the context (chunk_count = 1)",
                                                                      "no: 40,000-char chunks, 2,000 overlap, one digest",
                                                                      "call per chunk, digests concatenated (map-reduce)"], "decision")
    s.box(L, 756, LW, 170, "Three structured model calls, in sequence", ["grounding system prompt (src/prompts/analysis.py)",
                                                                         "1  Summary",
                                                                         "2  ResearchGaps  (each gap carries its evidence)",
                                                                         "3  LiteratureReview  (prior work the paper discusses)",
                                                                         "schema sent as JSON Schema, extra fields forbidden"], "current")
    s.box(L, 956, LW, 100, "Validate every reply  (Pydantic)", ["truncated or malformed -> refused (502), never repaired",
                                                                "insufficient_evidence fields let the model decline"], "current")
    s.box(L, 1086, LW, 80, "AnalysisResponse  ->  browser", ["+ provenance: provider, model, fallback_used, elapsed ms"], "current")
    for y1, y2 in [(196, 226), (326, 356), (456, 486), (566, 606), (726, 756), (926, 956), (1056, 1086)]:
        s.arrow([(L + LW / 2, y1), (L + LW / 2, y2 - 4)])
    s.text(L + LW / 2 + 14, 592, "miss", size=13, fill="#334155")

    M, MW = 620, 400
    s.box(M, 480, MW, 92, "Cache hit", ["stored analysis returned", "cache_hit = true · no model call"], "decision")
    s.arrow([(L + LW, 526), (M - 4, 526)], "hit", label_at=(590, 516))
    s.box(M, 756, MW, 170, "RoutedLLMProvider (per request)", ["primary = owner's choice (system_settings)",
                                                               "fallback = the other provider",
                                                               "switches at most once per analysis,",
                                                               "only for rate limits / transient failures",
                                                               "a disabled provider is never constructed"], "current")
    s.arrow([(L + LW, 841), (M - 4, 841)])
    s.box(M, 956, MW, 100, "analysis_cache  (write on success only)", ["keyed by content hash + analysis version",
                                                                      "a failure is never cached"], "external")
    s.arrow([(L + LW, 1006), (M - 4, 1006)])

    R, RW = 1080, 480
    s.box(R, 700, RW, 84, "Anthropic API", ["Claude (default claude-opus-5)"], "external")
    s.box(R, 830, RW, 84, "Groq API", ["Qwen 3.6 27B (qwen/qwen3.6-27b)"], "external")
    s.arrow([(M + MW, 800), (R - 4, 750)])
    s.arrow([(M + MW, 870), (R - 4, 870)])
    s.box(R, 956, RW, 210, "Library  (only when the user saves)", ["POST /api/papers -> papers + analyses rows,",
                                                                    "written as the signed-in user; RLS scopes rows",
                                                                    "POST /api/reviews/cross reads the STORED",
                                                                    "analyses of 2+ papers (not the PDFs),",
                                                                    "makes one model call, and writes",
                                                                    "literature_reviews + literature_review_papers"], "external")
    s.arrow([(L + LW, 1126), (600, 1126), (600, 1190), (R + RW / 2, 1190), (R + RW / 2, 1170)],
            "user clicks Save to library", label_at=(820, 1182))
    s.text(40, 1222, "The PDF itself is not stored: papers.storage_path exists in the schema but is unused.", size=13, fill="#64748b")
    s.legend(R, 140, ["current", "external", "decision"])
    return s


# ---------------------------------------------------------------------------
# 4. Provider routing and fallback
# ---------------------------------------------------------------------------
def ai_pipeline() -> Svg:
    s = Svg(1600, 820, "ResearchForge: provider routing and fallback",
            "src/rag/llm/router.py. One switch per analysis, and only for failures another vendor could plausibly fix.")
    s.box(60, 130, 330, 120, "Build router for this request", ["read owner's primary (system_settings)", "read enabled providers",
                                                                "unreadable setting -> env default"], "current")
    s.box(460, 130, 330, 120, "Call the primary", ["generate_structured(...)", "or generate_text(...) for digests"], "current")
    s.arrow([(390, 190), (456, 190)])
    s.box(860, 130, 300, 120, "Success", ["model_provider = primary", "fallback_used = false"], "current")
    s.arrow([(790, 170), (856, 170)], "ok", label_at=(823, 160))

    s.box(460, 330, 330, 150, "Is the error retryable?", ["whitelist in is_retryable():", "LLMRateLimitError  -> yes",
                                                          "bare LLMError (5xx, timeout)  -> yes", "anything else -> no"], "decision")
    s.arrow([(625, 250), (625, 326)], "error", label_at=(655, 295), anchor="start")
    s.box(60, 350, 330, 130, "Raise the real error", ["LLMCredentialsError -> 503", "LLMResponseError -> 502", "no fallback configured -> raise"], "error")
    s.arrow([(460, 405), (394, 405)], "no", label_at=(427, 395))

    s.box(860, 330, 330, 150, "Switch to the fallback", ["only if it is enabled", "stays switched for every later", "call in this analysis"], "current")
    s.arrow([(790, 405), (856, 405)], "yes", label_at=(823, 395))
    s.box(1260, 330, 300, 150, "Fallback result", ["recorded as produced by", "the fallback provider", "fallback_used = true"], "current")
    s.arrow([(1190, 380), (1256, 380)], "ok", label_at=(1223, 370))
    s.box(1260, 540, 300, 110, "Both failed", ["one LLMError naming both", "vendors' messages; no 3rd try"], "error")
    s.arrow([(1025, 480), (1025, 595), (1256, 595)], "error", label_at=(1140, 585))

    s.box(60, 560, 700, 150, "Why these rules (from the module docstring)", [
        "Per-call failover would let different sections be written by different models,",
        "making the stored \"model used\" a fiction. Retrying a bad PDF, a validation failure",
        "or a missing key on a second vendor spends a second quota to get the same error",
        "and hides the real cause. The whitelist means a new error type is not retryable by default.",
    ], "neutral")
    s.legend(820, 580, ["current", "decision", "error"])
    return s


# ---------------------------------------------------------------------------
# 5. Database relationships
# ---------------------------------------------------------------------------
def database() -> Svg:
    s = Svg(1600, 960, "ResearchForge: database relationships",
            "Supabase Postgres, built by six additive migrations (src/db/migrations/001 to 006). Every table has RLS enabled.")
    s.box(640, 120, 320, 100, "auth.users  (Supabase)", ["id  ·  managed by Supabase Auth", "passwords never reach app tables"], "external", center=True)
    s.box(60, 300, 380, 230, "papers", ["`id uuid PK", "`user_id DEFAULT auth.uid()", "`title, filename, file_size_bytes", "`page_count, status",
                                        "`authors, year  (not populated)", "`storage_path    (unused)", "RLS: user_id = auth.uid()"], "current")
    s.box(510, 300, 400, 250, "analyses", ["`id uuid PK", "`paper_id -> papers ON DELETE CASCADE", "`user_id DEFAULT auth.uid()",
                                           "`summary, research_gaps,", "`literature_review  jsonb", "`model_used, model_provider,",
                                           "`fallback_used, processing_time_ms, cache_hit", "RLS: user_id = auth.uid()"], "current")
    s.box(980, 300, 380, 200, "literature_reviews", ["`id uuid PK", "`user_id DEFAULT auth.uid()", "`title, model_used", "`content jsonb, paper_count",
                                                     "RLS: user_id = auth.uid()"], "current")
    s.box(700, 610, 440, 160, "literature_review_papers", ["`review_id -> literature_reviews CASCADE", "`paper_id  -> papers ON DELETE RESTRICT",
                                                           "restrictive policy: both sides owned", "deleting a reviewed paper -> 409"], "current")
    s.box(1180, 610, 380, 160, "analysis_cache", ["`content_hash + analysis_version", "`summary, gaps, review jsonb + provenance",
                                                  "shared by content, not by user", "written only after a valid analysis"], "current")
    s.box(1180, 120, 380, 140, "system_settings / app_owners", ["`active_ai_provider, enabled_ai_providers", "readable by signed-in users",
                                                               "writable only by an owner", "never holds a secret"], "current")
    s.box(60, 610, 560, 160, "chunks  (scaffolding)", ["`paper_id, chunk_index, content", "`embedding vector(1024)  ·  pgvector",
                                                       "table and RLS policy exist; nothing writes or reads it"], "planned", tag="PLANNED")
    s.arrow([(250, 530), (250, 606)], dashed=True)
    s.arrow([(510, 400), (444, 400)], "many : 1", label_at=(477, 390))
    s.arrow([(920, 606), (1100, 504)], "many : 1", label_at=(1060, 570))
    s.arrow([(720, 606), (720, 578), (360, 578), (360, 534)], "many : 1", label_at=(540, 568))
    s.arrow([(700, 220), (250, 220), (250, 296)], "owns", label_at=(470, 210))
    s.arrow([(800, 220), (800, 296)], "owns", label_at=(830, 262), anchor="start")
    s.arrow([(900, 220), (1170, 220), (1170, 296)], "owns", label_at=(1030, 210))
    s.legend(60, 800, ["current", "external", "planned"])
    return s


DIAGRAMS = {
    "architecture": architecture,
    "workflow": workflow,
    "data-flow": data_flow,
    "ai-pipeline": ai_pipeline,
    "database": database,
}


def find_chrome() -> str | None:
    for candidate in (
        shutil.which("chrome"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ):
        if candidate and pathlib.Path(candidate).exists():
            return candidate
    return None


def main() -> int:
    chrome = find_chrome()
    for name, build in DIAGRAMS.items():
        svg = build()
        svg_path = HERE / f"{name}.svg"
        svg_path.write_text(svg.render(), encoding="utf-8")
        print("wrote", svg_path.name)
        if not chrome:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            page = pathlib.Path(tmp) / "page.html"
            page.write_text(
                f'<html><body style="margin:0">{svg.render()}</body></html>', encoding="utf-8"
            )
            subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 f"--user-data-dir={tmp}/profile", "--force-device-scale-factor=2",
                 f"--window-size={svg.w},{svg.h}", f"--screenshot={HERE / (name + '.png')}",
                 page.as_uri()],
                check=True, capture_output=True,
            )
        print("rendered", name + ".png")
    if not chrome:
        print("Chrome not found: SVGs written, PNGs not rendered.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
