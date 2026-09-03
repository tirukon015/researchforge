<div align="center">

<img src="app/public/brand/researchforge-full.png" alt="ResearchForge. Explore, Analyze, Innovate" width="380">

**AI Research Assistant**

[![Next.js](https://img.shields.io/badge/next.js-16-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/fastapi-backend-009688)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776ab)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-114%20passing-brightgreen)](tests/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[Live application](https://researchforge.rukon.dev) ·
[Documentation](docs/DOCUMENTATION.md) ·
[API](docs/API.md) ·
[Setup](docs/SETUP.md)

</div>

---

> **Status: working MVP, deployed.** Upload a paper and get a summary, research
> gaps and a literature review. **Nothing is saved yet.** Analysis is stateless,
> and results are lost when the tab is reloaded. See
> [feature status](docs/DOCUMENTATION.md#feature-status).

## What it does

ResearchForge reads an academic PDF and produces three things:

1. **A structured summary.** Research problem, methodology, key findings,
   conclusion.
2. **A research gap analysis.** What the paper leaves open, why it matters, and
   the evidence in the paper that supports calling it a gap.
3. **A literature review.** The prior work the paper itself discusses, organised
   into themes, comparisons and future directions.

## The principle that shapes everything

**Every claim must be grounded in the uploaded paper.**

Where a paper does not support a section, ResearchForge says so instead of
writing something plausible. A position paper with no methodology produces a
summary that names methodology as unsupported, not an invented method. A gap is
shown with the evidence it rests on, because that evidence is the only thing
separating an identified gap from an invented one.

This is enforced in three places: the system prompt, the response schema's
`insufficient_evidence` fields, and an interface that prints them.

## Core features

| | |
| --- | --- |
| Upload | Drag and drop or file picker. PDF only, 25 MB limit, validated twice. |
| Extraction | pypdf. Scanned and encrypted files are rejected rather than guessed at. |
| Long papers | Papers over 400,000 characters are chunked automatically. Shorter ones are analysed whole, which preserves cross section context. |
| Analysis | Three separate schema constrained model calls, each validated on return. |
| Workspace | Tabbed results with copy actions and honest empty states. |
| Health | A live indicator reading the real `/health` endpoint. |
| Themes | Light and dark, following the operating system preference. |
| Responsive | Works from mobile to desktop. |

## Technology

| Layer | Choice |
| --- | --- |
| Frontend | Next.js 16 App Router, React 19, TypeScript strict, plain CSS |
| Backend | Python 3.12 or newer, FastAPI, Pydantic |
| PDF | pypdf. Pure Python, BSD licensed, installs identically everywhere. |
| AI | Google Gemini `gemini-3.7-flash` by default. Anthropic also implemented. |
| Hosting | One Vercel project running both services behind one origin |
| Database | Supabase Postgres with pgvector. **Designed, not connected.** |

## Architecture

```
                    Browser
                       |
                       v
        https://researchforge.rukon.dev
                       |
              Vercel routing (vercel.json)
                       |
        +--------------+--------------+
        |                             |
        v                             v
   /  and the rest             /health and /api/*
   Next.js service              FastAPI service
                                       |
                          +------------+------------+
                          |            |            |
                          v            v            v
                    PDF extraction  Prompts   LLM provider
                                                     |
                                                     v
                                             Google Gemini API
```

Both services share one origin, so the frontend calls the API with a relative
path. That is what makes the custom domain, the `vercel.app` domain and every
preview URL work from the same build. Details in
[ARCHITECTURE](docs/ARCHITECTURE.md).

## How it works

1. The user selects a PDF. The browser checks type, emptiness and size.
2. The file is posted to `/api/analyze`.
3. The backend checks the real byte count and verifies the PDF signature.
4. Text is extracted. A file with no text layer is rejected with `422`.
5. Long papers are chunked and digested; ordinary papers go through whole.
6. Three model calls run in sequence: summary, gaps, literature review.
7. Each reply is validated. A truncated or malformed answer is refused, never
   partially rendered.
8. One JSON response is returned and the workspace renders it.

Expect one to three minutes. The backend function allows 300 seconds.

## Quick start

Requires Python 3.12 or newer, Node 20 or newer, and a Gemini API key.

```bash
git clone https://github.com/tirukon015/researchforge.git
cd researchforge

# Backend
python3.12 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                # then set GEMINI_API_KEY
uvicorn src.main:app --reload --port 8000

# Frontend, in a second terminal
cd app
npm install
npm run dev
```

Open `http://localhost:3000`. The indicator at the top right should read
"Backend online". Full instructions in [SETUP](docs/SETUP.md).

## Environment

Minimum for local analysis:

```
APP_ENV=development
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Every variable is documented in [ENVIRONMENT](docs/ENVIRONMENT.md). Secrets are
server side only and never reach the browser.

## Testing

```bash
pytest                     # 231 tests, fully offline, no API key required
ruff check src tests       # lint
cd app && npm run build && npm run typecheck
```

The suite never touches the network and never spends a token. Model calls are
replaced by a fake provider through FastAPI's dependency overrides.

## Deployment

One Vercel project, `researchforge`, serving `researchforge.rukon.dev`.

**The project is not linked to GitHub.** Pushing does not build anything.
Production is updated with:

```bash
vercel deploy --prod
```

See [DEPLOYMENT](docs/DEPLOYMENT.md).

## AI provider

Gemini `gemini-3.7-flash` by default, chosen because a Vercel function has a
300 second ceiling and a Flash tier model with thinking turned up completes
three calls inside it. `LLM_MODEL` switches to `gemini-2.5-pro` for deeper
reasoning with no code change.

Both providers sit behind `src/rag/llm/base.py`, so switching vendors is one
environment variable and adding one is a single new file.

## Database

**Not connected.** No Supabase project is configured and nothing is persisted.

What exists: two additive migrations, a storage independent repository
interface, a Supabase implementation, and the request and response models.
What is missing: a Supabase project, its credentials, and the API routes that
would use them. See [DATABASE](docs/DATABASE.md).

## Known limitations

1. **Nothing is saved.** Reloading the tab discards the analysis.
2. **The free AI tier is small.** One analysis costs three provider requests, so
   the daily allowance runs out quickly.
3. **No OCR.** Scanned papers have no text layer and are rejected.
4. **Single paper scope.** The literature review covers the prior work one paper
   discusses. It does not search a corpus, and the interface says so.
5. **No authentication and no rate limiting.** Acceptable only while the
   application stores nothing.

## Documentation

| Document | Contents |
| --- | --- |
| [DOCUMENTATION](docs/DOCUMENTATION.md) | Full reference and feature status |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Technical architecture and lifecycles |
| [API](docs/API.md) | Every endpoint, request and response |
| [DATABASE](docs/DATABASE.md) | Schema, RLS, and connection status |
| [SETUP](docs/SETUP.md) | Local development |
| [DEPLOYMENT](docs/DEPLOYMENT.md) | Vercel, domain, verification |
| [ENVIRONMENT](docs/ENVIRONMENT.md) | Every environment variable |
| [SECURITY](docs/SECURITY.md) | Secrets, CORS, uploads, database security |
| [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) | Symptom, cause, check, fix |
| [PROJECT_STRUCTURE](docs/PROJECT_STRUCTURE.md) | Repository layout |

Project rules are in [CLAUDE.md](CLAUDE.md); milestones and decisions are in
[PROJECT_PLAN.md](PROJECT_PLAN.md).

## Licence

MIT. See [LICENSE](LICENSE).
