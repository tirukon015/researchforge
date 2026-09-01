# Deployment

## Current production

| | |
| --- | --- |
| Platform | Vercel |
| Project | `researchforge` |
| Team | RPOMS |
| Custom domain | `https://researchforge.rukon.dev` |
| Also serving | `researchforge-ten.vercel.app`, `researchforge-rpoms.vercel.app` |
| Repository | `github.com/tirukon015/researchforge` |
| Git integration | **Not configured** |

## The most important fact

**The Vercel project is not linked to the GitHub repository.** Pushing to
`main` does not build anything. Production is updated only by running the CLI
from a local working copy:

```bash
vercel deploy --prod
```

If production looks out of date after a push, this is almost always why.
Confirm with:

```bash
vercel project inspect researchforge
```

A linked project reports a `link` object. This one reports `null`.

## One project, two services

`vercel.json` declares two services and the routing between them:

```json
{
  "services": {
    "frontend": { "root": "app/", "framework": "nextjs" },
    "backend": {
      "root": "./",
      "framework": "fastapi",
      "entrypoint": "src.main:app",
      "functions": { "src/main.py": { "maxDuration": 300 } }
    }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/health",   "destination": { "service": "backend" } },
    { "source": "/(.*)",     "destination": { "service": "frontend" } }
  ]
}
```

Order matters. The catch all `/(.*)` is last, so it only receives what the two
specific rules did not.

`maxDuration: 300` is required. An analysis makes three model calls and
routinely takes one to three minutes, which is well past the default ceiling.

### How the two services communicate

They do not call each other. They share an **origin**, and the browser talks to
both.

Because `/health` and `/api/*` resolve on whatever host served the page, the
frontend uses a **relative** API path in production. This is the single most
important deployment decision in the project, and getting it wrong has already
caused one outage. See `NEXT_PUBLIC_API_BASE_URL` in
[ENVIRONMENT](ENVIRONMENT.md).

### Python packaging on Vercel

Vercel's Python builder runs `uv`, which prefers `pyproject.toml` over
`requirements.txt` when both exist. `pyproject.toml` therefore needs a
`[project]` table with runtime dependencies, and `[tool.uv] package = false`,
because ResearchForge is an application rather than an installable library.
Without those, the build fails with "No `project` table found".

The function excludes `app/`, `venv/`, `tests/`, `data/`, `models/`,
`notebooks/`, `results/`, `docs/` and bytecode, so the frontend source is not
shipped inside the Python bundle.

## Custom domain

`researchforge.rukon.dev` is attached to the `researchforge` project and
verified. It is an alias of the current production deployment, exactly like the
`vercel.app` URLs, so all three serve the same build.

The apex domain `rukon.dev` is registered outside the RPOMS team scope, so
`vercel domains inspect researchforge.rukon.dev` reports no access. That is
expected and does not affect serving. To confirm the attachment, query the
project's domains through the Vercel API instead.

## Environment variables

Set in Vercel Production:

```
GEMINI_API_KEY
LLM_PROVIDER
LLM_MODEL
LLM_EFFORT
CORS_ALLOWED_ORIGINS
APP_ENV
DEBUG
```

Deliberately not set: `NEXT_PUBLIC_API_BASE_URL`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`.

**Environment changes require a redeploy.** Backend values are read at cold
start, and `NEXT_PUBLIC_` values are compiled into the bundle at build time.
Adding a variable in the dashboard changes nothing until the next deploy.

## CORS

`CORS_ALLOWED_ORIGINS` is an explicit comma separated list, never `*`. In
production it names the custom domain and the `vercel.app` domain.

Because the frontend calls the API on its own origin, CORS is not on the
critical path for normal use. It matters for anything calling the API from
another origin, and it is kept correct so that path works too.

## Deployment procedure

From the repository root, with a clean working tree:

```bash
# 1. Confirm the target before doing anything
cat .vercel/project.json      # must read "researchforge"
git remote get-url origin     # must read tirukon015/researchforge

# 2. Validate
pytest
cd app && npm run build && npm run typecheck && cd ..

# 3. Commit and push, for history
git add -A
git commit -m "..."
git push origin main

# 4. Deploy, which is what actually updates production
vercel deploy --prod
```

Step 4 is not optional and step 3 does not replace it.

## Verifying production

```bash
# Health, on the custom domain
curl https://researchforge.rukon.dev/health
# {"status":"ok","app_name":"ResearchForge","version":"0.1.0","environment":"production"}

# FastAPI is answering under /api
curl -o /dev/null -w "%{http_code}\n" https://researchforge.rukon.dev/api/analyze
# 405, because the route requires POST

# The frontend is served
curl -o /dev/null -w "%{http_code}\n" https://researchforge.rukon.dev/

# No localhost leaked into the client bundle
curl -s https://researchforge.rukon.dev/ \
  | grep -o '/_next/static/chunks/[^"]*\.js' | sort -u \
  | while read -r c; do curl -s "https://researchforge.rukon.dev$c" \
      | grep -o 'localhost:8000'; done
# no output is the correct result
```

Confirm the domain is pointing at the deployment you just made:

```bash
vercel inspect <deployment-url>
```

The `Aliases` block should list `researchforge.rukon.dev`.

## Common deployment failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| Production shows old code after a push | No Git integration. The push built nothing. | Run `vercel deploy --prod`. |
| "Backend offline" on the custom domain only | `NEXT_PUBLIC_API_BASE_URL` set to an absolute host, making the custom domain a cross origin caller. | Remove the variable and redeploy. |
| Build fails with "No `project` table found" | `pyproject.toml` is missing its `[project]` table. | Restore it. `uv` prefers it over `requirements.txt`. |
| Analysis times out around 60 seconds | `maxDuration` missing or too low. | Confirm `maxDuration: 300` in `vercel.json`. |
| A new environment variable has no effect | Values are read at cold start and at build time. | Redeploy. |
| `/docs` returns 404 in production | Correct behaviour. Disabled when `APP_ENV=production`. | Run locally to read the docs. |

## Rollback

```bash
vercel ls researchforge          # list recent deployments
vercel inspect <older-url>       # confirm it is the one you want
vercel promote <older-url>       # point production at it
```

Rolling back does not change environment variables, so a rollback will not
undo a configuration change.
