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

ResearchForge reads an academic PDF and produces three things, into a research
library that is **private to your account**:

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
| Landing page | A public page at `/` describing the product. No account needed to read it. |
| Accounts | Email and password, through Supabase Auth. Sign up, sign in, forgot password, reset password. Passwords never reach the ResearchForge database. |
| Google sign-in | "Continue with Google" on both account screens, completing at `/auth/callback`. |
| Two AI providers | Anthropic Claude and Groq Qwen 3.6 27B. The owner picks one as primary; the other automatically becomes the fallback. |
| Automatic fallback | Once per analysis, and only for rate limits and temporary provider failures. Never for a bad PDF, a validation failure or a missing key, which would fail identically on either vendor. |
| Recorded provenance | Every new analysis stores which provider and model ACTUALLY produced it, whether the fallback was used, and how long it took. |
| Private libraries | Every paper, analysis and review belongs to one account. Enforced by Postgres Row Level Security, not by the interface. |

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

### AI architecture

Two providers, one primary, automatic fallback to the other.

```
owner picks Claude  ->  primary Claude,  fallback Groq
owner picks Groq    ->  primary Groq,    fallback Claude
```

There is no third "auto" option, because the fallback is not a choice: it is
whichever provider was not chosen. The primary is stored in
`system_settings.active_ai_provider` and only the owner can change it, enforced
by the API and again by Row Level Security.

**Fallback happens once per analysis, and only for retryable failures** - a
rate limit or a temporary outage. It does not happen for an invalid PDF, a
schema validation failure, or a missing API key: those fail the same way on
either vendor, and retrying would spend a second quota to produce the same
error while hiding the real cause.

Every new analysis records the provider and model that ACTUALLY produced it. If
Claude was primary but Groq wrote the result, the stored row says Groq.

Gemini has been retired from the active workflow. `gemini_provider.py` remains
on disk because analyses produced by it are still in the database; nothing
routes to it, and its historical records are unchanged.

**This is not RAG.** The pipeline is whole-document extraction followed by
grounded generation. Jina, pgvector and the `chunks` table exist as scaffolding
that nothing calls.

## AI providers

Analysis needs at least one of these. Whichever is primary, the other is the
automatic fallback:

```
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_KEY     # console.anthropic.com
GROQ_API_KEY=YOUR_GROQ_KEY               # console.groq.com
```

Optional, with sensible defaults: `ANTHROPIC_MODEL` (`claude-opus-5`),
`GROQ_MODEL` (`qwen/qwen3.6-27b`).

To sign in and save papers you also need a Supabase project. Backend (`.env`):

```
SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SECRET_KEY
```

Frontend (`app/.env.local`):

```
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
```

The two `NEXT_PUBLIC_` values are public by design and are compiled into the
browser bundle. The **service role key must never** be given a `NEXT_PUBLIC_`
prefix: it bypasses Row Level Security, and in a browser bundle it would hand
every user's library to anyone who read the page source.

Every variable is documented in [ENVIRONMENT](docs/ENVIRONMENT.md). Secrets are
server side only and never reach the browser.

## Testing

```bash
pytest                     # 439 tests, fully offline, no API key required
cd app && npm test         # 16 frontend tests (redirect + open-redirect logic)

# Optional: prove the provider keys and model IDs are real. Makes ONE small
# call per provider, so it is opt-in rather than part of the default suite.
RESEARCHFORGE_LIVE_PROVIDER_TEST=1 pytest tests/test_provider_smoke.py -v
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

## Database and data isolation

**Connected, with ownership enforced by Postgres.** Three additive migrations
build the schema; migration 003 is the one that makes each account's library
private.

The mechanism, in one paragraph: the browser signs in with Supabase and gets an
access token. It sends that token to the FastAPI backend, which passes it
straight through to Postgres. Postgres resolves `auth.uid()` to that person, and
the Row Level Security policies (`user_id = auth.uid()`) decide which rows exist
at all. The service-role key, which would bypass all of that, is used for **no
data request**. The consequence is that a forgotten `WHERE` clause returns
nothing rather than everything, and changing an id in a URL reaches a `404`.

See [DATABASE](docs/DATABASE.md#row-level-security).

## Known limitations

1. **The free AI tier is small.** One analysis costs three provider requests, so
   the daily allowance runs out quickly.
2. **No OCR.** Scanned papers have no text layer and are rejected.
3. **Single paper scope.** The literature review covers the prior work one paper
   discusses. It does not search a corpus, and the interface says so.
4. **No rate limiting of our own.** Analysis is behind sign-in, so it cannot be
   spent anonymously, but a signed-in account is not throttled beyond whatever
   the model provider imposes.
5. **Rows created before accounts existed are unreachable.** They are preserved,
   not deleted, and are deliberately not assigned to an owner nobody can prove.
   See [DATABASE](docs/DATABASE.md#claiming-pre-authentication-rows).

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
