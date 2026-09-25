# ResearchForge: Project Documentation

> **Scope of this document.** One consolidated technical record of ResearchForge as it exists
> in this repository and on the live deployment, written for the portfolio case study. It
> **sits beside** the existing reference docs (`DOCUMENTATION.md`, `ARCHITECTURE.md`,
> `API.md`, `DATABASE.md`, `SECURITY.md` and the rest) and replaces none of them.
>
> **Evidence rule.** Every claim is marked by where it came from:
> **[code]** read in source · **[test]** from the test suite run on 2026-09-25 ·
> **[live]** observed on `researchforge.rukon.dev` on 2026-09-25 ·
> **[results]** from `results/evaluation/` · **[docs]** from existing project docs.
> Anything that could not be checked is labelled **NOT VERIFIED**, and anything intended but
> not built is labelled **PLANNED**.
>
> **Baseline.** Local `main` at `33bc740` (2026-09-06). GitHub `main` is one commit ahead
> (`fbcd5a7`, 2026-09-10), and that commit only deletes `CLAUDE.md`. The application code is
> identical.

---

## 01. Executive Summary

ResearchForge is a web application that reads one academic PDF and returns three structured,
schema-validated analyses: a **summary**, a **research-gap analysis** in which every gap carries
quoted evidence from the paper, and a **literature review** of the prior work the paper
discusses. Signed-in users save results to a **private library** isolated by PostgreSQL Row
Level Security, and can build one **cross-paper literature review** from two or more saved
papers. **[code][live]**

It was built as the capstone for BIT4543 Artificial Intelligence (University of Cyberjaya) by
one developer. It is **deployed and live** at `https://researchforge.rukon.dev`
(`/health` → `{"status":"ok","environment":"production","library":true,"auth":true}` on
2026-09-25). **[live]**

What it is **not**: it is not a RAG system. There are no embeddings and no retrieval on any
production path. The whole paper is the model's context. **[code]**

## 02. Project Overview

| | |
|---|---|
| Type | University capstone, also a public portfolio project |
| Course | BIT4543 Artificial Intelligence, project #17 |
| Developer | Sole developer (every commit has one author) **[git]** |
| Period | 2026-08-11 (first commit) to 2026-09-06 (last local commit) **[git]** |
| Repository | `github.com/tirukon015/researchforge`, MIT licence |
| Live | `researchforge.rukon.dev`, also `researchforge-ten.vercel.app` **[docs]** |
| Shape | Next.js 16 frontend and FastAPI backend in **one Vercel project, one origin** **[code: vercel.json]** |

## 03. Problem Statement

When an AI summariser fails, it rarely produces nothing. It produces something **plausible
that the source does not support**: a methodology for a position paper, or a confidently stated
gap with no basis. For research use this is worse than no answer, because a reader who does
not already know the paper cannot tell it apart from a correct one. The project brief also
required upload, summaries, research gaps, literature reviews and a usable application.
**[docs: CLAUDE.md §1, README]**

## 04. Target Users

Students and researchers who need to triage a paper quickly: what it claims, what it leaves
open, and which prior work it builds on. The owner-only settings panel serves the person
operating the deployment. **[code]** No user research or usage figures exist. **NOT VERIFIED:
real user numbers.**

## 05. Objectives

1. Upload a research paper (PDF). ✅
2. Generate a summary. ✅
3. Identify research gaps. ✅
4. Produce a literature review. ✅ Single-paper, plus cross-paper over saved analyses.
5. Ship a usable, deployed research-assistant application. ✅
6. Project rule: every generated claim is grounded in the supplied text, and the system says
   "insufficient evidence" rather than guessing. ✅ Enforced in the prompt, the schema,
   validation and the UI. **[code]**

## 06. Requirements

**Functional (implemented):** PDF upload up to 25 MB; text extraction; three analyses;
accounts (email/password, Google); private library (save, list, search, filter, sort, open,
delete); cross-paper review; owner AI configuration; light and dark themes; responsive layout.
**[code][live]**

**Non-functional (implemented):**
- Fits a 300-second serverless ceiling (`maxDuration: 300`). **[code: vercel.json]**
- The test suite runs offline and spends no tokens. **[test]**
- Secrets live only on the server. **[code]**
- Per-user isolation is enforced in the database, not only in the application. **[code]**

**Planned in `PROJECT_PLAN.md`, not built:** F3 embeddings/indexing, F8 grounded Q&A chat,
F9 chunk-level citations, F10 export. **[docs: PROJECT_PLAN.md progress table]**

## 07. User Journey

See the [workflow diagram](screenshots/case-study/diagrams/workflow.png).

1. **Sign in** at `/sign-in` (email and password, or Google) → Supabase session.
2. **Upload** a PDF on `/dashboard`. The browser checks type, emptiness and size.
3. **Analyse**: `POST /api/analyze`, typically 1–3 minutes. The UI lists the steps but does
   not claim progress, because the backend reports none.
4. **Read** the result in tabs: Summary, Research Gaps, Literature Review, Paper Information.
   Each section has a copy button.
5. **Save to library**: `POST /api/papers`. The analysis is passed back, not re-run.
6. **My Papers** (`/papers`): search, status filter, sort, open, delete.
7. **Workspace** (`/workspace`): tick two or more saved papers.
8. **Cross-paper review** on `/literature-review`: one model call over the stored analyses.
9. **Read and copy.** There is no file export.

Branches: rejected upload (413/422); cache hit (same text, stored result, no model call);
provider error (429/502/503). **[code][live]**

## 08. Feature Inventory

| Feature | Status | Evidence |
|---|---|---|
| Public landing page | **COMPLETED** | `app/src/app/page.tsx`, screenshot 01 |
| Email/password sign-up, sign-in, forgot and reset password | **COMPLETED** | `app/src/app/*`, `lib/auth.tsx` |
| Google sign-in (PKCE) | **COMPLETED** (code). Button is live. A full Google round trip was **NOT VERIFIED** this session | `GoogleButton.tsx`, `auth/callback` |
| PDF upload with client and server validation | **COMPLETED** | `UploadPanel.tsx`, `api/analyze.py`, 31 tests |
| PDF extraction (pypdf), cleaning, scanned/encrypted rejection | **COMPLETED** | `ingestion/pdf.py` |
| Long-paper map-reduce (>400,000 chars) | **COMPLETED**. Not exercised live; unit-tested | `ingestion/chunking.py`, `services/analysis.py` |
| Summary / gaps / literature review (3 structured calls) | **COMPLETED** | `services/analysis.py`, [live] |
| Insufficient-evidence fields | **COMPLETED** | `schemas/analysis.py` |
| Provider routing: primary plus one fallback | **COMPLETED** | `rag/llm/router.py`, 36 tests, [live] |
| Owner choice of primary, per-provider on/off | **COMPLETED** | `api/owner.py`, migration 006, screenshot 10 |
| Provenance recording (provider, model, fallback, time, cache hit) | **COMPLETED** | migrations 004/005, screenshots 04, 07 |
| Content-hash analysis cache | **COMPLETED** | `db/analysis_cache.py`, [live] cache hit 2026-09-25 |
| Private library (save/list/stats/open/delete) | **COMPLETED** | `api/papers.py`, 35 tests |
| Row Level Security isolation | **COMPLETED** | migrations 002/003, [results] `isolation_test.txt` |
| Cross-paper literature review | **COMPLETED** | `api/reviews.py`, `services/cross_review.py`, screenshot 09 |
| Reopen saved cross-paper reviews in the UI | **IN PROGRESS**. API routes exist; no UI calls `listReviews()` | `lib/api.ts:610`, grep |
| Account settings (name, password, sign-out) | **COMPLETED** | `AccountSettings.tsx` |
| Light / dark / system theme | **COMPLETED** | `lib/theme.tsx`, screenshot 11 |
| Responsive layout | **COMPLETED** | screenshots 12/13 |
| Health endpoint with capability flags | **COMPLETED** | `main.py`, [live] |
| Copy-to-clipboard per section | **COMPLETED** | `CopyButton.tsx` |
| Export (Markdown/PDF/BibTeX) | **PLANNED** (F10, E4) | PROJECT_PLAN |
| Grounded Q&A chat | **PLANNED** (F8) | PROJECT_PLAN |
| Embeddings (Jina v3, 1024-d) | **PENDING**. Interface and request builder written and tested offline; HTTP call deliberately not implemented | `rag/embeddings/jina.py`, 29 tests |
| pgvector `chunks` table / retrieval / RAG | **PENDING**. Schema only; nothing reads or writes it | migration 001 |
| OCR for scanned papers | **PLANNED / not in scope**. Scanned PDFs are rejected | `ingestion/pdf.py` |
| Bibliographic metadata (authors, year) | **PENDING**. Columns exist, never populated | migration 001 |
| PDF file storage (Supabase Storage) | **PENDING**. `storage_path` and bucket config exist, unused | `config.py`, grep |
| Application-level rate limiting | **PLANNED**. `RATE_LIMIT_PER_MINUTE` is in `.env.example` but not read by config | grep |
| Google Gemini provider | **DEPRECATED**. Kept for historical rows; not routed | `gemini_provider.py`, `router.PROVIDERS` |

## 09. Technology Stack

| Layer | Technology | Version (pinned/declared) |
|---|---|---|
| Frontend | Next.js (App Router), React, TypeScript strict, plain CSS | next ^16.3.4, react ^19.2.8, typescript ^7.0.2 |
| Auth client | @supabase/supabase-js (auth only) | ^2.115.0 |
| Backend | Python, FastAPI, Pydantic, pydantic-settings, uvicorn | fastapi 0.141.1; verified on Python 3.14.7 |
| PDF | pypdf (BSD-3) | 6.16.2 |
| LLM SDKs | anthropic; Groq through its OpenAI-compatible REST endpoint via httpx (no Groq SDK) | anthropic 1.2.0 |
| Database/Auth | Supabase Postgres + Supabase Auth, reached over REST (PostgREST/GoTrue) | — |
| Tests | pytest, Vitest; lint with ruff | pytest 9.1.1, vitest ^5 |
| Hosting | Vercel, one project, two services (`vercel.json` `services`) | — |

`psycopg`, `sqlalchemy` and `pgvector` are pinned in `requirements.txt` from the Milestone-2
design, but the running code reaches the database through Supabase's REST API. **[code]**

## 10. System Architecture

![System architecture](screenshots/case-study/diagrams/architecture.png)

- **One origin.** `vercel.json` rewrites `/api/*` and `/health` to the FastAPI service and
  everything else to Next.js. The frontend therefore calls the API with a **relative path**,
  so the custom domain, the `vercel.app` domain and every preview URL all work from one build.
  `NEXT_PUBLIC_API_BASE_URL` is deliberately left unset in production. **[code][docs]**
- **External services:** Supabase Auth, Supabase Postgres, the Anthropic API, the Groq API.
- **Scaffolding:** Jina embeddings and the pgvector `chunks` table (dashed in the diagram).
- **Retired:** Google Gemini.

## 11. Frontend Architecture

- `app/src/app/*`: App Router routes: `/`, `/sign-in`, `/sign-up`, `/forgot-password`,
  `/reset-password`, `/auth/callback`, `/dashboard`, `/papers`, `/papers/[id]`, `/workspace`,
  `/literature-review`, `/settings`. The build shows 15 routes: 14 static and 1 dynamic. **[test: build]**
- `lib/api.ts`: typed API client. It attaches the Supabase access token and maps status codes
  to user-facing messages, including `Retry-After` and quota exhaustion.
- `lib/auth.tsx`, `lib/session.tsx`: session state with an explicit `loading` state, so a
  reload never flashes the sign-in page.
- `lib/library.tsx`: library data plus the **selection context** shared by Workspace and
  Literature Review. It lives in memory only, so it does not survive a reload.
- `components/AuthGate.tsx`: a UX redirect only. Its own comment says it is **not** the
  security boundary.
- `lib/supabase.ts`: a lazily built client with `flowType: "pkce"` pinned, so tokens never
  appear in URLs.

## 12. Backend Architecture

- `src/main.py`: app wiring, CORS (explicit origin list), `/`, `/health`. `/docs` is hidden in
  production.
- `src/api/`: `analyze.py`, `papers.py`, `reviews.py`, `owner.py`, `auth.py`.
- `src/services/`: `analysis.py` (pipeline), `cross_review.py`, `content_hash.py`.
- `src/ingestion/`: `pdf.py` (validate, extract, clean), `chunking.py` (map-reduce split).
- `src/rag/llm/`: `base.py` (`LLMProvider`, error types), `router.py`, vendor providers.
  The folder name is historical: it contains no retrieval.
- `src/rag/embeddings/`: provider interface and Jina request construction (unused).
- `src/db/`: `supabase.py` (REST repository), `repository.py`, `analysis_cache.py`,
  `migrations/001–006`.
- `src/prompts/analysis.py`: versioned prompts (`PROMPT_VERSION = "1.2.0"`).

## 13. Database Architecture

![Database](screenshots/case-study/diagrams/database.png)

Six additive migrations (`CREATE` / `ALTER … ADD COLUMN IF NOT EXISTS` only):

| Migration | Adds |
|---|---|
| 001 | `papers`, `chunks` (`vector(1024)`), RLS enabled |
| 002 | `analyses`, `literature_reviews`, `literature_review_papers`, owner policies |
| 003 | `user_id DEFAULT auth.uid()`, restrictive policy on review links, `chunks` policy, indexes |
| 004 | `app_owners`, `system_settings`, provenance columns on `analyses` |
| 005 | `analysis_cache`, `analyses.cache_hit` |
| 006 | `enabled_ai_providers` setting (provider availability) |

Pre-authentication rows (2 papers, 2 analyses, 1 review) keep `user_id = NULL`. They are
unreachable but deliberately not deleted. **[docs: DATABASE.md, CLAUDE.md §14]**

## 14. API Architecture

| Method & path | Purpose | Auth |
|---|---|---|
| `GET /health` | Liveness and `library`/`auth` booleans | Public |
| `GET /` | API descriptor | Public |
| `POST /api/analyze` | Upload and analyse a PDF | Bearer |
| `POST /api/papers` · `GET /api/papers` · `GET /api/papers/stats` · `GET/DELETE /api/papers/{id}` | Library | Bearer, RLS |
| `POST /api/reviews/cross` · `GET /api/reviews` · `GET/DELETE /api/reviews/{id}` | Cross-paper reviews | Bearer, RLS |
| `GET /api/owner/status` · `GET/PUT /api/owner/ai-config` | Owner AI configuration | Bearer; owner-only writes |

Error contract: **401** not signed in · **404** missing *or someone else's* row (never 403,
which would confirm the row exists) · **409** deleting a paper a review depends on ·
**413** too large · **422** unusable PDF · **429** provider rate limit, with `Retry-After` /
`X-Quota-Exhausted` · **502** unusable model output · **503** no credentials or no database.
Nothing expected returns 500. **[code]** Full reference: `docs/API.md`.

## 15. Search / Retrieval Architecture

**There is no retrieval.** Search in the product means the library's title/filename match,
passed as `GET /api/papers?search=…&status=…&sort=…` and run by the backend against the
user's own rows (RLS-scoped, max 200 characters, paginated up to 100 rows). There is no
full-text search inside papers, no semantic search, no embeddings
and no vector queries. The Jina provider can build a request body but never sends one, and the
`chunks` table is never written. **[code]** This is stated in the UI, the README and here.

## 16. AI Architecture

![Provider routing](screenshots/case-study/diagrams/ai-pipeline.png)

| Question | Exact answer |
|---|---|
| Models / providers | **Anthropic** (default `claude-opus-5`) and **Groq** (default `qwen/qwen3.6-27b`), both overridable by env var. Production on 2026-09-25: **Groq primary, Claude fallback**, both enabled **[live: owner settings]** |
| Where AI is used | (1) the three analysis passes; (2) one digest call per chunk, for papers over 400,000 chars only; (3) one cross-paper review call |
| Input | A grounding system prompt, plus a task prompt containing the **whole extracted, cleaned paper text** (or concatenated digests). For a cross-review: each paper's **stored** summary, findings, limitations and themes, clipped to 4,000 chars per section |
| Output | JSON conforming to `Summary`, `ResearchGaps`, `LiteratureReview` (Pydantic). Anthropic uses `messages.parse(output_format=Model)`; Groq uses `response_format: json_object` with the schema in the prompt. Both are validated with Pydantic on return |
| Retrieval | None |
| Citations | Gaps carry an `evidence` field quoting or paraphrasing the paper. There are **no page- or chunk-level citations** (F9 planned) |
| Stored? | Only when the user saves (`analyses` row). Successful analyses are also written to `analysis_cache`, keyed by content hash. Failures are never cached |
| Fallback | At most one switch per analysis, only for `LLMRateLimitError` or bare transient `LLMError` (whitelist). Never for credential, validation or bad-PDF errors. If both providers fail, one error names both |
| Provenance | `model_provider`, `model_used`, `fallback_used`, `processing_time_ms`, `cache_hit` recorded per analysis |
| Prompt-injection stance | The system prompt frames paper text as **data, never instructions** |
| Limitations | Grounded ≠ correct: nothing verifies that a summary is accurate. No labelled benchmark exists. Groq's free tier (7,000 input TPM) cannot take a whole paper, so the fallback is the normal path today **[results]** |

**No claim is made that the output is factually correct.**

## 17. Document Processing

1. The size is checked on the real byte count (25 MB default).
2. The `%PDF` signature is verified, so the declared content type is only a hint.
3. Encrypted PDFs get one empty-password decrypt attempt, then are rejected.
4. pypdf extracts every page. Fewer than 200 usable characters is treated as a scanned PDF
   and rejected with 422.
5. Cleaning: ligatures normalised, hyphenated line breaks rejoined, spaces collapsed but
   **newlines kept**, nothing removed.
6. Up to 400,000 chars the whole paper is the context. Above that: 40,000-char chunks with
   2,000 overlap, split on paragraph, then sentence, then hard boundaries, with one digest
   call per chunk. **[code]**

The PDF itself is **not stored**. **[code]**

## 18. Citation / Reference System

ResearchForge does **not** generate formatted citations or a bibliography, and has no export.
What it does have:
- **Evidence per research gap**: a required schema field containing the paper's wording.
- **Literature review attribution**: prior work is attributed to the authors *as the uploaded
  paper cites them*. Cited works are **not** fetched or checked, and the review says so in its
  scope note (screenshot 06).
- **Cross-paper attribution**: each theme names the paper it came from (screenshot 09), and
  `literature_review_papers` records which papers a review used.

No academic-accuracy claim is made for any reference.

## 19. Authentication

Supabase Auth. The browser signs in directly and receives a short-lived JWT. Every API call
sends `Authorization: Bearer <token>`. `require_user` verifies it by calling Supabase's
`/auth/v1/user` endpoint instead of checking the signature locally, which honours
revocation. A 5-second in-process cache bounds the window in which a signed-out token still
works; a live test showed a 30-second cache was too long. **[code][results: logout_window.txt]**

## 20. Authorization

- **Row Level Security** on every table (`user_id = auth.uid()`). The backend makes data
  requests **as the user**, with the anon key plus the user's token, so Postgres applies the
  policies. The service-role key is used for **no** data request. **[code][docs]**
- A missing ownership filter therefore returns **nothing**, not everything.
- Another user's row returns **404**, never 403.
- Owner-only AI configuration is checked by the API **and** by RLS policies on
  `system_settings`.
- Verified live with two real accounts: 26/26 checks passed. **[docs: CLAUDE.md §14,
  results/evaluation/isolation_test.txt]**

## 21. Security

See `docs/SECURITY.md` for the full treatment. Key points:
- Secrets exist only as server env vars. The two `NEXT_PUBLIC_*` values are the public URL and
  the anon key by design.
- A guard refuses a *publishable* key placed in the service-role slot. That failure used to
  be silent (an empty library). It has 22 tests.
- `require_user` runs **before** the upload is read, so anonymous callers learn nothing about
  the server's configuration and cannot make it read 25 MB.
- CORS uses an explicit origin list, never `*`.
- PKCE for OAuth, so no tokens appear in URLs.
- `/health` reports booleans, never URLs or keys.
- Paper text is treated as data in the prompt (a prompt-injection mitigation, **not a
  guarantee**).
- **Gap:** the app does not rate-limit its own users (analysis is sign-in gated only).

## 22. Data Flow

![Data flow](screenshots/case-study/diagrams/data-flow.png)

## 23. Integrations

Supabase Auth (email/password, Google OAuth), Supabase Postgres (PostgREST), the Anthropic
Messages API, the Groq OpenAI-compatible API, and Vercel (hosting). Jina is written but not
connected; Gemini is retired. No other integrations exist.

## 24. UI/UX

Research-dashboard layout with top navigation (Dashboard, My Papers, Literature Review,
Workspace, Settings). Tabs for each analysis, copy buttons, honest empty and error states
("not connected" versus "no papers"), a status pill that reads the real `/health`,
light/dark/system themes, and a collapsed menu on mobile. Screenshots 01–13 show these.
**Known copy defect:** the dashboard's "How ResearchForge works" panel still says the paper
goes to **Gemini**. **[live 2026-09-25]**

## 25. Error Handling

Typed exceptions (`LLMError`, `LLMRateLimitError`, `LLMCredentialsError`,
`LLMResponseError`, `PdfExtractionError`, `RepositoryError` and its subclasses) are mapped to
the status codes in §14. Truncated or malformed model output is **refused, never repaired**.
Library reads degrade one migration level at a time when the schema is behind the code.
Cache failures degrade to "no cache", never to a broken upload. SDK-internal retries on 429
are switched off, so costs are not multiplied silently. **[code]**

## 26. Performance

Measured on the deployed system **[results/evaluation/summary.txt, cache_test.txt]**:

| Measure | Value |
|---|---|
| New analysis, full paper (n=10 successful runs, 5 papers) | median **98.8 s**, range 72.6–115.2 s |
| Cache hit (same text) | **2.7–3.2 s** |
| Extraction | 6–19 pages, 23,767–69,097 chars, all analysed as one chunk |

This session's demo papers (3 pages each) finished in under about 90 s, including the Groq
refusal and the switch to Claude. **[live, approximate, observed not benchmarked]**
Analyses run sequentially by design, to limit peak rate-limit pressure.

## 27. Development Process

Planning came first: the rules (`CLAUDE.md`), a `PROJECT_PLAN.md` with milestones, numbered
decisions (D3 layout, D5 LLM, D6 embeddings, D7 hosting) and risks. The work then moved in
small milestones, with tests after each one and conventional commit messages (`feat:`,
`fix:`, `docs:`, `test:`). One developer throughout.

## 28. Git History

41 commits on local `main`, plus one GitHub-only commit. Milestones:

| Date | Milestone |
|---|---|
| 2026-08-11 | Structure, rules and plan; FastAPI foundation with `/health` and tests (M1); initial schema migration (M2); embedding decision D6 made, revisited and re-locked to Jina v3 at 1024 dims |
| 2026-09-01 | **Analysis MVP**: upload → extraction → three structured passes, stateless |
| 2026-09-02 | Same-origin API fix for the custom domain; Gemini provider; frontend rebuilt as a research dashboard; library end to end; Supabase layer tests |
| 2026-09-03 | Library queries and rate-limit handling hardened; publishable-key guard |
| 2026-09-04 | Authentication, private libraries and landing page; Google sign-in; **Claude + Groq** routing with owner-only config; PKCE and logout fixes; account settings; content-hash reuse; per-migration degradation; provider availability |
| 2026-09-06 | Five-paper evaluation corpus and evidence; diagrams; report and presentation deliverables |
| 2026-09-10 | (GitHub only) `CLAUDE.md` removed from the public repo |

## 29. Challenges

| # | Problem | Context | Solution | Why | Trade-off | Result | Limitation |
|---|---|---|---|---|---|---|---|
| 1 | **RLS was inert** | The backend used a key that bypasses RLS; every test passed | Make requests *as the user* (anon key + user JWT) | The database then enforces isolation even if code forgets | One auth round trip per request (5 s cache) | 26/26 live isolation checks | Pre-auth rows are unreachable, not reassigned |
| 2 | **Provider rate limits** | Gemini, then Groq free tiers too small; 429s looked like 500s | Vendor-neutral 429 mapping, `Retry-After`, SDK retries off, one fallback per analysis | Honest errors; bounded cost | The fallback is the normal path while the primary is small | 10/10 completions via Claude in the evaluation | Effectively single-provider |
| 3 | **Custom domain showed "Backend offline"** | An absolute API base URL made the custom domain cross-origin | Same-origin relative calls; env var unset in prod | Every domain works from one build | Local dev needs the env var set | Works on all domains | — |
| 4 | **Schema ahead of migrations** | New columns selected before a migration ran → every read failed | Retry, degrading one migration level at a time | A rollout can't take the library down | More code paths | Reads survive | Missing columns show as empty |
| 5 | **CDN hid real errors** | The custom-domain CDN replaced origin error bodies | Diagnose against the origin directly | Exposed the real Groq TPM message | Manual step | Evaluation finding identified | — |
| 6 | **Silent misconfiguration** | A publishable key in the private slot → empty library | Guard that refuses it, with 22 tests | Fail loudly | — | Detected at startup | — |
| 7 | **Token revocation window** | 30 s cache kept signed-out tokens working | Cut to 5 s after a live logout test | Bounded, stated window | More auth calls | ≤5 s | Not zero |
| 8 | **Cache vs measurement** | Content-keyed cache returned old results during evaluation | Clear rows before measuring; record it | The cache is correct; the experiment wasn't | — | Clean evaluation | Worth knowing for any benchmark |

**[code][git][results][docs]**

## 30. Solutions

The solutions share one principle: **fail in the honest direction.** Refuse output rather
than repair it, return an explicit 429/503 rather than a generic 500, return 404 rather than
leak existence, report "not connected" rather than an empty list, and record provenance rather
than assume it.

## 31. Testing

Run on 2026-09-25, Windows, Python 3.14.7, Node 24.19.0:

| Check | Result |
|---|---|
| `pytest` | **522 passed, 5 skipped** (live-provider smoke tests, opt-in), 1 deprecation warning from `google-genai`, 29.2 s |
| `ruff check src tests` | All checks passed |
| `npm test` (Vitest) | **16 passed** (1 file: redirect and open-redirect logic) |
| `npm run typecheck` | Passed |
| `npm run build` | Passed: 15 routes |

Tests per module: auth 61 · LLM providers 49 · Supabase repository 48 · rate limit 42 ·
router 36 · library 35 · analysis 31 · provider availability 30 · Groq 30 · content hash 30 ·
embeddings 29 · owner 28 · key-type guard 22 · analysis cache 22 · ownership 20 · main 9 ·
provider smoke 5. The tests call no paid API; providers are faked through FastAPI dependency
overrides.

Beyond unit tests: live scripts against production (`results/evaluation/isolation_test.txt`,
`cache_test.txt`, `logout_window.txt`) and the five-paper evaluation. **No end-to-end browser
test suite exists.**

## 32. Deployment

A single Vercel project, `researchforge`, deployed with `vercel deploy --prod`. The Vercel
project is **not linked to GitHub**, so a push does not deploy. **[docs]** The backend function
has a 300 s `maxDuration`. Live status verified 2026-09-25 through `/health`. **NOT VERIFIED:
the exact commit currently deployed.** The live UI includes the features of the latest commits
(provider availability, reuse, provenance), which is consistent with `33bc740`.

## 33. Current Status

Deployed MVP, working end to end: accounts, private library, three analyses, cross-paper
review, owner AI configuration. The evaluation is complete. No active development since
2026-09-06, apart from the GitHub-side removal of `CLAUDE.md` on 2026-09-10.

## 34. Known Limitations

1. Not RAG; no retrieval or embeddings.
2. Effectively single-provider (Groq's free tier < one paper).
3. Grounded ≠ accurate; there is no accuracy benchmark.
4. The evaluation covers 5 English papers from one field, run once per configuration, assessed by the author.
5. No OCR.
6. The literature review covers only the prior work a paper itself cites.
7. No export beyond copy.
8. Saved cross-paper reviews can't be reopened in the UI.
9. No app-level rate limiting.
10. No bibliographic metadata extraction.
11. The dashboard copy still mentions Gemini.
12. Revoked sessions stay valid for up to about 5 s.
13. Stale docs: `README.md` still says "Nothing is saved yet", shows a 114-test badge and names
    Gemini as default; `CLAUDE.md` §14 says 431 tests and "no provider key". Both predate the
    current state. (Not edited here: CLAUDE.md §4 requires approval before overwriting.)
14. `.env.example` omits `GROQ_API_KEY`, `GROQ_MODEL`, `ANTHROPIC_MODEL` and `OWNER_EMAIL`,
    which `config.py` reads, and lists `RATE_LIMIT_PER_MINUTE`, which it doesn't.

## 35. Future Improvements

- **Small, ready:** a saved-reviews list (routes exist); fix the Gemini copy; refresh the README
  and `.env.example`.
- **Configuration:** a primary provider whose limits accept a whole paper.
- **PLANNED (PROJECT_PLAN):** F3 embeddings and retrieval, F8 grounded Q&A, F9 page-level
  citations, F10 export, E4 BibTeX, E7 hybrid search.
- **Quality:** a labelled evaluation set, if accuracy is ever to be claimed.

## 36. Portfolio Case Study

See [`CASE_STUDY.md`](CASE_STUDY.md) for the narrative version, and the live portfolio page
`/work/researchforge/case-study`.

## 37. Skills Demonstrated (each backed by code in this repo)

Full-stack web development (Next.js + FastAPI); LLM integration with structured output and
schema validation; multi-provider routing and failure semantics; Postgres schema design and
additive migrations; Row Level Security and auth (Supabase, PKCE); API design with a precise
error contract; PDF ingestion; offline-first automated testing with dependency injection;
serverless deployment under a time limit; production debugging; honest technical writing.

## 38. Evidence / Traceability

| Claim | Where to check |
|---|---|
| Not RAG | `src/services/analysis.py` (no retrieval call), `src/rag/embeddings/jina.py` (no HTTP) |
| Fallback rules | `src/rag/llm/router.py::is_retryable`, `tests/test_router.py` |
| RLS as the user | `src/db/supabase.py`, `src/db/migrations/002–003`, `results/evaluation/isolation_test.txt` |
| Cache | `src/api/analyze.py`, `src/db/analysis_cache.py`, `results/evaluation/cache_test.txt` |
| Latency figures | `results/evaluation/summary.txt`, `runs.json` |
| Groq capacity | `results/evaluation/groq_capacity.json` |
| Test counts | `pytest --collect-only -qq` (2026-09-25) |
| Live config | Screenshot 10 (owner settings, 2026-09-25) |
| Screenshots and demo data | `docs/SCREENSHOT_PLAN.md`, `docs/screenshots/case-study/demo-data/` |
| Diagrams | `docs/screenshots/case-study/diagrams/build_diagrams.py` |
