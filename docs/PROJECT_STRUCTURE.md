# Project structure

Generated from the actual repository. Directories that exist only to hold a
`.gitkeep` placeholder are marked as such, so nothing here implies more than
is really present.

```
researchforge/
├── app/                        Next.js frontend
│   ├── public/
│   │   └── brand/              Official ResearchForge logo assets
│   │       ├── researchforge-mark.png            transparent mark
│   │       ├── researchforge-mark-contained.png  opaque mark
│   │       └── researchforge-full.png            full lockup
│   ├── src/
│   │   ├── app/                App Router routes
│   │   │   ├── layout.tsx      root layout, metadata, providers
│   │   │   ├── page.tsx        dashboard, the canonical homepage
│   │   │   ├── globals.css     the entire design system, plain CSS
│   │   │   ├── icon.png        favicon, generated from the mark
│   │   │   ├── apple-icon.png  touch icon, generated from the opaque mark
│   │   │   ├── papers/         My Papers
│   │   │   ├── literature-review/
│   │   │   └── settings/
│   │   ├── components/
│   │   │   ├── AppShell.tsx        navigation shell
│   │   │   ├── UploadPanel.tsx     upload, validation, progress
│   │   │   ├── ResultsView.tsx     tabbed analysis workspace
│   │   │   ├── AnalysisSections.tsx  shared result renderers
│   │   │   ├── BackendStatus.tsx   live health indicator
│   │   │   ├── EmptyState.tsx
│   │   │   ├── CopyButton.tsx
│   │   │   └── Icons.tsx           inline SVG icon set
│   │   └── lib/
│   │       ├── api.ts          typed backend client
│   │       └── session.tsx     in-memory session state
│   ├── next.config.mjs
│   ├── package.json
│   └── tsconfig.json
│
├── src/                        Python FastAPI backend
│   ├── main.py                 app wiring, GET / and GET /health
│   ├── config.py               all settings, read from the environment
│   ├── api/
│   │   └── analyze.py          POST /api/analyze
│   ├── ingestion/              PDF extraction and long-paper chunking
│   ├── rag/
│   │   ├── llm/                generation providers
│   │   │   ├── base.py             the LLMProvider contract
│   │   │   ├── gemini_provider.py  Google Gemini
│   │   │   └── anthropic_provider.py
│   │   └── embeddings/         embedding providers, request building only
│   ├── prompts/
│   │   └── analysis.py         versioned prompt templates
│   ├── schemas/
│   │   ├── analysis.py         what the model produces
│   │   └── library.py          what the database would store
│   ├── services/
│   │   └── analysis.py         the three-call analysis pipeline
│   └── db/                     data layer, NOT wired to any endpoint
│       ├── repository.py       storage-independent interface
│       ├── supabase.py         Supabase implementation over PostgREST
│       └── migrations/
│           ├── 001_initial_schema.sql
│           └── 002_analysis_and_reviews.sql
│
├── tests/                      pytest suite, 231 tests, fully offline
│   ├── test_main.py
│   ├── test_analysis.py
│   ├── test_llm_providers.py
│   ├── test_embeddings.py
│   └── pdf_fixtures.py
│
├── docs/                       this documentation
├── data/                       placeholder only, holds .gitkeep files
├── models/                     placeholder only
├── notebooks/                  placeholder only
├── results/                    placeholder only
│
├── vercel.json                 two-service deployment and routing
├── requirements.txt            full local Python environment
├── pyproject.toml              runtime deps, pytest, ruff config
├── .env.example                backend environment template
├── CLAUDE.md                   permanent project rules
├── PROJECT_PLAN.md             milestones and decision log
└── README.md
```

## What the important files do

| Path | Responsibility |
| --- | --- |
| `vercel.json` | Declares two services in one project and routes `/api/*` and `/health` to FastAPI, everything else to Next.js. |
| `src/main.py` | Creates the FastAPI app, adds CORS, mounts the analysis router, owns `GET /` and `GET /health`. |
| `src/config.py` | Every setting the backend reads. Nothing is hard coded and no secret has a default. |
| `src/api/analyze.py` | The only analysis endpoint. Maps failures onto status codes the frontend can act on. |
| `src/services/analysis.py` | Extracts text, chunks long papers, then makes three separate model calls. |
| `src/rag/llm/base.py` | The provider contract. No vendor type appears outside a provider file. |
| `src/prompts/analysis.py` | The anti-fabrication system prompt and the three task prompts, versioned. |
| `app/src/lib/api.ts` | The only place the frontend performs network calls. |
| `app/src/lib/session.tsx` | Holds the current analysis in memory so it survives route changes. |
| `app/src/app/globals.css` | The whole design system as CSS custom properties. There is no CSS framework. |

## Directories that are placeholders

`data/`, `models/`, `notebooks/` and `results/` exist because the course
structure requires them. They contain `.gitkeep` files and, in two cases, a
short `README.md`. No data, model weights, notebooks or measured results are
committed.
