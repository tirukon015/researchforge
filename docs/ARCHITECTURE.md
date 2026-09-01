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
