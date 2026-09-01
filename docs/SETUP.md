# Local setup

These instructions were followed on Windows with Python 3.14.7 and Node
24.19.0. They work the same on macOS and Linux with the paths adjusted.

## Prerequisites

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.12 or newer | `pyproject.toml` sets `requires-python = ">=3.12"`. Verified on 3.14.7. |
| Node.js | 20 or newer | Next.js 16 requires it. Verified on 24.19.0. |
| npm | bundled with Node | |
| Git | any recent version | |

A Gemini API key is needed to analyse a paper. Everything else, including the
whole test suite, runs without one.

## 1. Clone

```bash
git clone https://github.com/tirukon015/researchforge.git
cd researchforge
```

## 2. Backend

Create a virtual environment and install dependencies.

macOS and Linux:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.12 -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` is the full local environment: the server, the test runner,
the linter, and the database drivers reserved for a later milestone.
`pyproject.toml` lists only what the deployed function imports at runtime, and
Vercel builds from that.

## 3. Environment file

```bash
cp .env.example .env
```

Open `.env` and set at least:

```
APP_ENV=development
DEBUG=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

`.env` is git ignored and must never be committed. Full reference in
[ENVIRONMENT](ENVIRONMENT.md).

## 4. Frontend

```bash
cd app
npm install
```

The frontend needs no environment file in development. `app/src/lib/api.ts`
defaults to `http://localhost:8000` when `NODE_ENV` is `development`.

## 5. Run both services

Two terminals.

Terminal one, backend, from the repository root:

```bash
uvicorn src.main:app --reload --port 8000
```

Terminal two, frontend, from `app/`:

```bash
npm run dev
```

Open `http://localhost:3000`.

## 6. Verify

| Check | How | Expected |
| --- | --- | --- |
| Backend is alive | `curl http://localhost:8000/health` | `{"status":"ok", ...}` |
| API documentation | open `http://localhost:8000/docs` | Interactive OpenAPI page |
| Frontend is alive | open `http://localhost:3000` | Dashboard loads |
| The two are connected | look at the top right of the dashboard | "Backend online", with version and environment |
| Analysis works | upload a PDF and click Analyse paper | Results after one to three minutes |

If the indicator reads "Backend offline", the backend is not running or is on a
different port. See [TROUBLESHOOTING](TROUBLESHOOTING.md).

## Development commands

Backend, from the repository root with the virtual environment active:

```bash
pytest                      # 114 tests, fully offline, no API key needed
ruff check src tests        # lint
ruff format src tests       # format
uvicorn src.main:app --reload --port 8000
```

Frontend, from `app/`:

```bash
npm run dev                 # development server
npm run typecheck           # tsc --noEmit
npm run build               # production build
npm run start               # serve the production build
```

### A note on `npm run typecheck`

Run it **after** `npm run build`, not before. Next.js generates route types into
`.next/`, and `tsconfig.json` includes them. Running the typecheck against
stale generated types reports errors that do not exist. If it reports something
implausible, delete `app/tsconfig.tsbuildinfo` and run it again; that file is a
git ignored incremental cache.

## Database setup

Optional and currently not connected. The application runs fully without it,
with the library features disabled. To enable it, follow "Enabling the
database" in [DATABASE](DATABASE.md).

## AI provider setup

Default is Google Gemini.

1. Create a key at `https://aistudio.google.com/apikey`.
2. Put it in `.env` as `GEMINI_API_KEY`.
3. Leave `LLM_PROVIDER=gemini` and `LLM_MODEL=gemini-3.7-flash`.

The free tier has a low daily request allowance and one analysis costs three
requests. If analysis fails with a quota message, that is the cause.

To use Anthropic instead, set `LLM_PROVIDER=anthropic` and provide
`ANTHROPIC_API_KEY`. `LLM_MODEL` can be left alone: a model name belonging to
the other vendor is ignored in favour of the selected provider's default.

## Production build locally

```bash
cd app
npm run build
npm run start
```

This serves the production bundle, where the API base URL is a relative path.
The backend is therefore expected on the **same** origin, which it will not be
locally, so the dashboard will show "Backend offline". That is correct
behaviour, not a fault. Use `npm run dev` to exercise the full flow locally.
