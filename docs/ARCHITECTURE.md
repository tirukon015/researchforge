# Architecture

## Shape of the system

ResearchForge is **one Vercel project running two services**. A Next.js
frontend and a FastAPI backend share a single origin, and `vercel.json` decides
which service answers which path.

```
                    Browser
                       |
                       v
        https://researchforge.rukon.dev
                       |
              Vercel edge routing
              (rewrites in vercel.json)
                       |
        +--------------+--------------+
        |                             |
        v                             v
   /  and everything          /health and /api/*
        |                             |
   Next.js service              FastAPI service
   (app/, framework:            (root, framework:
    nextjs)                      fastapi, src.main:app)
                                       |
                          +------------+------------+
                          |            |            |
                          v            v            v
                    PDF extraction  Prompts   LLM provider
                    (pypdf)                   (Gemini or
                          |                    Anthropic)
                          v                        |
                    long-paper chunking            v
                          |                  Google Gemini API
                          +------------+-----------+
                                       |
                                       v
                            Analysis response (JSON)
                                       |
                                       v
                               Frontend workspace
```

The single origin is the important detail. Because the frontend and the API
answer on the same host, the frontend calls the API with a **relative path**,
which is correct on the custom domain, on the `vercel.app` domain and on every
preview URL. Pinning it to one absolute host would make every other host a
cross origin caller.

## Frontend architecture

Next.js 16 App Router, React 19, TypeScript in strict mode. There is **no CSS
framework**: the entire design system lives in `app/src/app/globals.css` as CSS
custom properties, with light values on `:root` and a dark block that redefines
only the tokens.

| Layer | Responsibility |
| --- | --- |
| `app/src/app/*/page.tsx` | Routes. Each is a client component because each reads session state. |
| `app/src/app/*/layout.tsx` | Per route metadata. A client component cannot export metadata, so the segment layout carries it. |
| `app/src/components/` | Presentational components. None performs a network call. |
| `app/src/lib/api.ts` | The only place `fetch` is called. Owns the error vocabulary. |
| `app/src/lib/session.tsx` | In memory session state, shared across routes through React context. |

### Error vocabulary

`api.ts` maps every failure onto one of five kinds: `offline`, `rejected`,
`upstream`, `config`, `malformed`. The interface chooses its wording from the
kind rather than by matching on message text, so a backend message can change
without breaking the frontend.

### Routes

| Route | Purpose |
| --- | --- |
| `/` | Dashboard. Upload, session overview, most recent analysis. |
| `/papers` | My Papers. Empty until persistence exists. |
| `/literature-review` | The literature review from the current analysis. |
| `/settings` | Application and provider information. |

All four are statically prerendered and work on a direct load or refresh.

## Backend architecture

FastAPI on Python 3.12 or newer. The application is deliberately thin: routing
and validation at the edge, decisions in services, vendor code confined to
provider files.

```
src/main.py            wiring, CORS, GET / and GET /health
    |
    +-- src/api/analyze.py      POST /api/analyze, status code mapping
            |
            +-- src/ingestion/pdf.py        extract and verify the PDF
            +-- src/ingestion/chunking.py   split only very long papers
            +-- src/services/analysis.py    the three call pipeline
                    |
                    +-- src/prompts/analysis.py   versioned prompt text
                    +-- src/rag/llm/base.py       the provider contract
                            |
                            +-- gemini_provider.py
                            +-- anthropic_provider.py
```

### Provider abstraction

`src/rag/llm/base.py` defines `LLMProvider` with three members: `model_name`,
`generate_structured`, and `generate_text`. Nothing outside a provider file
imports a vendor SDK or a vendor exception. `get_llm_provider` builds the
implementation named by `LLM_PROVIDER`.

This is why adding Gemini alongside Anthropic cost one new file and one branch,
and changed neither the pipeline, the API layer, nor the frontend.

Each provider translates vendor errors into project owned ones, so the API
layer can map credentials failures to `503` and everything else to `502`
without knowing which vendor is in use.

### Why three model calls

Summary, gap analysis and literature review are different cognitive tasks with
different evidence rules. One combined prompt makes the model interleave them
and the weakest section drags the others down. Three focused calls each get the
model's full attention, fail independently, and can be improved independently.

The cost is that one analysis is three requests against the provider's rate
limit.

### Long papers

A paper under `LONG_PAPER_CHAR_THRESHOLD` (400,000 characters, roughly 100,000
tokens) is analysed **whole**. Chunking is not the default because it loses the
cross section context that lets the model connect a limitation in section 6 to
a claim in section 3.

Above the threshold, the paper is split, each chunk is digested with a faithful
extraction prompt, and the digests are concatenated for the three analysis
calls. That is a map step followed by three reduce steps.

## Data architecture

**Currently stateless.** No database is connected. See [DATABASE](DATABASE.md)
for the full status and the intended schema.

The data access layer is written and follows the same pattern as the provider
abstraction: `src/db/repository.py` defines the interface, `src/db/supabase.py`
implements it over PostgREST, and no endpoint imports either yet.

## Deployment architecture

```
GitHub: tirukon015/researchforge
   |
   |  (no Git integration configured)
   |
   v
Local working copy  --->  vercel deploy --prod  --->  Vercel project
                                                       "researchforge"
                                                       (team RPOMS)
                                                             |
                                    +------------------------+
                                    |                        |
                        researchforge.rukon.dev    researchforge-ten.vercel.app
```

The Vercel project is **not linked to the GitHub repository**. Pushing does not
trigger a build. Production is updated by running the CLI from a local working
copy. See [DEPLOYMENT](DEPLOYMENT.md).

## Request lifecycle

A complete analysis, end to end:

1. The browser loads `/`. Next.js serves a prerendered page.
2. On mount, the frontend calls `GET /health`. Vercel rewrites this to the
   FastAPI service. The result drives the "Backend online" indicator.
3. The user selects a PDF. The frontend validates type, emptiness and size.
4. The frontend `POST`s `multipart/form-data` to `/api/analyze` with a ten
   minute timeout.
5. FastAPI reads the body and checks the real byte count against the limit.
6. `extract_document` verifies the PDF signature and extracts text with pypdf.
   A scanned PDF with no text layer is rejected with `422`.
7. If the text exceeds the threshold, it is chunked and each chunk is digested.
8. Three structured calls run in sequence: summary, gaps, literature review.
   Each is constrained by a JSON schema and validated on return.
9. The response is assembled and returned as one JSON document.
10. The frontend stores it in session state and renders the tabbed workspace.

Steps 7 to 9 are why the request takes one to three minutes. The backend
function is configured with `maxDuration: 300`.

## Data lifecycle

```
PDF in the browser
   |
   v  multipart upload
Backend memory
   |
   v  pypdf
Extracted text
   |
   v  three model calls
Analysis JSON
   |
   v  HTTP response
Frontend React state   <-- lives here until the tab is reloaded
   |
   X  no persistence
```

The uploaded file is never written to disk and never stored. It exists in
backend memory for the duration of the request.

---

## Case-study diagrams (added 2026-09-25)

Five diagrams drawn from the code at commit `33bc740`. They are generated by
`docs/screenshots/case-study/diagrams/build_diagrams.py` (SVG source plus PNG render), and each
box maps to code in this repository. Legend: solid blue = current, violet = external service,
dashed = planned scaffolding nothing calls, dotted = retired.

| Diagram | Shows |
|---|---|
| [System architecture](screenshots/case-study/diagrams/architecture.png) | One origin, two services, Supabase Auth/Postgres, Anthropic, Groq; Jina/pgvector planned; Gemini retired |
| [User workflow](screenshots/case-study/diagrams/workflow.png) | Sign in → upload → analyse → read → save → select → cross-paper review, with error and cache branches |
| [Data flow](screenshots/case-study/diagrams/data-flow.png) | One analysis from PDF bytes to response; no retrieval step |
| [Provider routing](screenshots/case-study/diagrams/ai-pipeline.png) | `RoutedLLMProvider`: whitelist, one switch per analysis |
| [Database](screenshots/case-study/diagrams/database.png) | Tables, foreign keys, RLS, planned `chunks` |

The existing Mermaid figures for the university report are still in `docs/report/diagrams/`.
See also `docs/PROJECT_DOCUMENTATION.md` and `docs/CASE_STUDY.md`.

---

## Maintenance quick reference (current state, 2026-09-26)

> **This section describes the application as it is today.** Parts of the document above
> were written for the stateless MVP (for example "no persistence", Gemini as the provider).
> Where they conflict, **this section and `PROJECT_SPEC.md` win**.

### Next.js (frontend, `app/`)
- Next.js 16 App Router, React 19, TypeScript `strict`, plain global CSS
  (`app/src/app/globals.css`). No Tailwind, no component library, no web fonts.
- **Server components:** `app/layout.tsx` (metadata, theme init script, providers), the
  landing page `app/page.tsx`, and one small `layout.tsx` per protected route that only
  exports `metadata`.
- **Client components:** every interactive page (`"use client"`), all of `components/`, and
  every `lib/*` provider. Rule: a page that needs metadata gets a server `layout.tsx` beside
  a client `page.tsx`, because client components can't export metadata.
- **Providers (outer → inner):** `ThemeProvider` → `AuthProvider` → `SessionProvider` →
  `SelectionProvider` → `AppShell`.
- **Data access:** only through `lib/api.ts` (typed fetch, bearer token from
  `setTokenReader`). Supabase JS is used **only for auth**, never for data.
- `next.config.mjs`: `reactStrictMode`, `images.unoptimized: true`.

### Python (backend, `src/`)
- FastAPI app in `src/main.py`; routers in `src/api/`; business logic in `src/services/`;
  vendor code isolated in `src/rag/llm/<vendor>_provider.py` behind `LLMProvider`.
- **Dependencies injected with `Depends`:** `require_user` → `get_library` / `get_provider`.
  Tests override `get_provider` with a fake, which is why no test spends tokens.
- Database access goes through `src/db/supabase.py` (PostgREST over httpx) **as the signed-in
  user**. The SQLAlchemy/psycopg pins in `requirements.txt` are unused by the running code.

### Request data flow
Browser → same-origin `/api/*` → Vercel rewrite → FastAPI → (Supabase Auth verify) →
service → provider router → Anthropic/Groq → Pydantic validation → JSON → browser. Library
writes happen only on an explicit save. Diagrams:
[data flow](screenshots/case-study/diagrams/data-flow.png).

### Environment variables (names only; values live in `.env` / Vercel)
- **Backend (read by `src/config.py`):** `APP_NAME`, `APP_ENV`, `DEBUG`, `BACKEND_PORT`,
  `CORS_ALLOWED_ORIGINS`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_EFFORT`, `LLM_MAX_OUTPUT_TOKENS`,
  `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_BASE_URL`,
  `GEMINI_API_KEY` (retired), `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, `OWNER_EMAIL`, `MAX_UPLOAD_SIZE_MB`, `ALLOWED_FILE_TYPES`,
  `LONG_PAPER_CHAR_THRESHOLD`, `LONG_PAPER_CHUNK_SIZE`, `LONG_PAPER_CHUNK_OVERLAP`,
  `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `JINA_API_KEY`
  (embedding values unused at runtime).
- **Frontend (public by design):** `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`; `NEXT_PUBLIC_API_BASE_URL` for local dev only (**unset in
  production**).
- `.env.example` currently lacks `GROQ_*`, `ANTHROPIC_MODEL` and `OWNER_EMAIL`, and lists
  unused names (`RATE_LIMIT_PER_MINUTE`, `RETRIEVAL_*`, `CHUNK_*`, `DATABASE_URL`). Treat
  `config.py` as authoritative.

### Deployment assumptions
- One Vercel project, `researchforge`: `services.frontend` (root `app/`, Next.js) and
  `services.backend` (FastAPI, `src.main:app`, `maxDuration` 300). Rewrites send
  `/api/(.*)` and `/health` to the backend and everything else to the frontend.
- **Not linked to GitHub:** deploy with `vercel deploy --prod`.
- Migrations are applied by hand in the Supabase SQL editor, in number order.

### Key decisions (see PROJECT_PLAN.md for the numbered log)
- D3 folder layout (`src/` backend, `app/` frontend) · D5 LLM behind an interface (now Claude
  + Groq) · D6 Jina 1024-d embeddings (locked, unused) · D7 one Vercel project, one origin ·
  RLS as the user (never the service role) · whole-document context instead of RAG · refuse
  invalid model output, never repair it.
