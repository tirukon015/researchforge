# Environment variables

Every variable below was traced to the code that reads it. Nothing here is
aspirational, and no real value appears anywhere in this file.

Backend variables are read by `src/config.py` through `pydantic-settings`, in
this order of priority:

1. Real environment variables, which is how production works.
2. A local `.env` file, which is how development works.
3. The defaults written in `src/config.py`.

Frontend variables must be prefixed `NEXT_PUBLIC_` to reach the browser, and
anything with that prefix is **compiled into the JavaScript bundle and is
visible to the whole internet**. Never put a secret behind it.

---

## Secrets

### `GEMINI_API_KEY`

| | |
| --- | --- |
| Purpose | Authenticates the Google Gemini API. |
| Required | Yes, when `LLM_PROVIDER=gemini`. |
| Used by | `src/rag/llm/gemini_provider.py`, through `Settings.gemini_api_key`. |
| Example | `YOUR_GEMINI_API_KEY` |
| Where | Local `.env`, and Vercel Production. |

Obtained from Google AI Studio. Without it, `POST /api/analyze` returns `503`
with a message naming this variable. Everything else, including the whole test
suite, runs without it.

### `ANTHROPIC_API_KEY`

| | |
| --- | --- |
| Purpose | Authenticates the Anthropic API. |
| Required | Only when `LLM_PROVIDER=anthropic`. |
| Used by | `src/rag/llm/anthropic_provider.py`. |
| Example | `YOUR_ANTHROPIC_API_KEY` |

Not set in production, because production runs on Gemini.

### `SUPABASE_SERVICE_ROLE_KEY`

| | |
| --- | --- |
| Purpose | Authenticates the backend to Supabase. |
| Required | No. The library is disabled without it. |
| Used by | `src/db/supabase.py`. |
| Example | `YOUR_SUPABASE_SERVICE_ROLE_KEY` |

**This key bypasses Row Level Security.** It is server side only. It must never
be given a `NEXT_PUBLIC_` prefix, returned by an endpoint, or written into a
log. Not currently set anywhere.

`SUPABASE_URL` is set in Vercel Production. It is a public project URL, not a
secret, and it is inert on its own: `has_database` requires both halves, so the
library stays disabled until the key is added too.

### `JINA_API_KEY`

| | |
| --- | --- |
| Purpose | Authenticates the Jina embeddings API. |
| Required | No. Embeddings are not wired into any endpoint. |
| Used by | `src/rag/embeddings/jina.py`. |
| Example | `YOUR_JINA_API_KEY` |

---

## Backend configuration

| Name | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `ResearchForge` | Reported by `GET /health`. |
| `APP_ENV` | `development` | Set to `production` to disable `/docs` and `/redoc`. Reported by `GET /health`. |
| `DEBUG` | `true` | Set `false` in production. |
| `BACKEND_PORT` | `8000` | Local development port only. Vercel ignores it. |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma separated list of origins allowed to call the API. Never `*`. |

`CORS_ALLOWED_ORIGINS` in production is set to the custom domain and the
`vercel.app` domain. Because the deployed frontend calls the API on its own
origin, CORS is not on the critical path, but the list is kept correct anyway.

## AI provider

| Name | Default | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `gemini` | Selects the implementation. Accepts `gemini` or `anthropic`. |
| `LLM_MODEL` | `gemini-3.7-flash` | The model to call. A name belonging to the other vendor is ignored in favour of the selected provider's default, so `LLM_PROVIDER` can be changed on its own. |
| `LLM_EFFORT` | `high` | How hard the model thinks: `minimal`, `low`, `medium`, `high`, `xhigh`, `max`. Gemini's scale stops at `high`, so `xhigh` and `max` map down to it. |
| `LLM_MAX_OUTPUT_TOKENS` | `16000` | Ceiling on one response. |

There is deliberately no temperature setting. Sampling parameters are rejected
by the model families in use. Control output with `LLM_EFFORT` instead.

## Long paper handling

| Name | Default | Purpose |
| --- | --- | --- |
| `LONG_PAPER_CHAR_THRESHOLD` | `400000` | Above this many characters, the paper is chunked instead of sent whole. |
| `LONG_PAPER_CHUNK_SIZE` | `40000` | Characters per chunk. |
| `LONG_PAPER_CHUNK_OVERLAP` | `2000` | Overlap so sentences are not cut mid idea. |

These are separate from `CHUNK_SIZE` and `CHUNK_OVERLAP`, which belong to the
future retrieval chunker. Reusing one setting for both would make a 1000
character long paper chunk fire hundreds of model calls per upload.

## Upload limits

| Name | Default | Purpose |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_MB` | `25` | Checked against the real byte count. |
| `ALLOWED_FILE_TYPES` | `application/pdf` | Comma separated. |

The frontend enforces the same 25 MB limit as a courtesy, so a user is not made
to wait for an upload that was never eligible.

## Database

| Name | Default | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | empty | Base URL of the Supabase project. |
| `SUPABASE_SERVICE_ROLE_KEY` | empty | See Secrets above. No data request uses it any more; it is read to decide whether a database is configured. |
| `OWNER_EMAIL` | empty | Bootstrap owner. A verified token whose email matches this may change global AI configuration. Compared SERVER-SIDE against the email Supabase verified, never against anything the browser sent. Optional: ownership properly lives in the `app_owners` table, and this exists only because that table starts empty. |
| `ANTHROPIC_API_KEY` | empty | **Required for analysis** when Claude is primary or fallback. Server-side only. |
| `ANTHROPIC_MODEL` | `claude-opus-5` | Claude model to use. Preferred over `LLM_MODEL`, which is shared across vendors and can be sent to the wrong one. |
| `GROQ_API_KEY` | empty | **Required for analysis** when Groq is primary or fallback. Server-side only. |
| `GROQ_MODEL` | `qwen/qwen3.6-27b` | Groq model to use. |
| `RESEARCHFORGE_LIVE_PROVIDER_TEST` | unset | Set to `1` to opt into `tests/test_provider_smoke.py`, which makes one real call per provider to prove the key and model ID work. Skipped otherwise, so the default suite stays offline and free. |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | Groq's OpenAI-compatible endpoint. |
| `LLM_PROVIDER` | `anthropic` | The STARTING primary. The live value is the owner's choice in `system_settings.active_ai_provider`, so switching providers is a setting rather than a redeploy. |
| `SUPABASE_ANON_KEY` | empty | **Required.** Public key. Sent as `apikey` alongside each signed-in user's own access token, which is what makes Postgres apply their Row Level Security policies. Also used to verify a token against `/auth/v1/user`. Without it the library routes answer `503` rather than falling back to a key that bypasses RLS. |
| `STORAGE_BUCKET` | `papers` | Private bucket for uploaded PDFs. |

`Settings.has_database` requires **both** the URL and the key. A URL without a
key cannot authenticate, and a key without a URL has nowhere to go, so
reporting "configured" on half a pair would turn a clear error into a confusing
timeout.

## Frontend

| Name | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | see below | Absolute base URL of the backend. |
| `NEXT_PUBLIC_SUPABASE_URL` | empty | **Required for sign-in.** The Supabase project address. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | empty | **Required for sign-in.** The publishable key. |

The default is chosen by build mode in `app/src/lib/api.ts`:

- **Development**: `http://localhost:8000`, because Next runs on port 3000 and
  uvicorn on port 8000, so they genuinely are separate origins.
- **Production**: the empty string, which makes every call a same origin
  relative path.

**Leave this unset in Vercel.** `vercel.json` already routes `/health` and
`/api/*` to the FastAPI service, so the API lives on whatever origin served the
page. Setting it to one absolute host makes every other host, including the
custom domain and every preview URL, a cross origin caller that the CORS
allowlist will block. That failure appears in the interface as "Backend
offline", and it has happened once already.

### The two Supabase values

Unlike `NEXT_PUBLIC_API_BASE_URL`, these two **must** be set in Vercel, for
Production *and* Preview. Without them the sign-in page says accounts are not
configured on this deployment, which is honest but not useful.

They are public on purpose. `NEXT_PUBLIC_` values are compiled into the
JavaScript bundle and visible to anyone who opens the page, and both of these
are safe there: the URL is a public address, and the anon key grants nothing on
its own because every table has Row Level Security enabled - a request carrying
only that key reads zero rows.

**The service-role key must never be given a `NEXT_PUBLIC_` prefix.** It
bypasses Row Level Security. In a browser bundle it would hand every user's
research library to anyone who opened the page and read the source.

The browser uses these for authentication only: signing in, signing out, and
resetting a password. Papers, analyses and reviews always go through the
FastAPI backend.

---

## Which variables belong where

### Local development

Copy `.env.example` to `.env` and fill in real values. `.env` is git ignored.

Minimum to analyse a paper locally:

```
APP_ENV=development
DEBUG=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

The frontend needs no `.env.local` at all in development. If you create one,
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` matches the built in default.

### Preview deployments

Preview builds share Production values unless a Preview specific value is set.
Because the frontend uses a relative API path, a preview deployment works on its
own URL with no extra configuration.

### Production

Currently set in the Vercel project:

```
GEMINI_API_KEY
LLM_PROVIDER
LLM_MODEL
LLM_EFFORT
CORS_ALLOWED_ORIGINS
APP_ENV
DEBUG
```

Deliberately **not** set: `NEXT_PUBLIC_API_BASE_URL` (see above),
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `JINA_API_KEY`.

Environment variables are read at cold start, and `NEXT_PUBLIC_` values are
compiled into the bundle at build time. **Changing any variable requires a
redeploy.**
