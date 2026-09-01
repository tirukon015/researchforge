# API reference

Every endpoint below was read from the source. The backend currently exposes
**three** routes and nothing else. Endpoints that appear in the project plan
but do not exist yet are listed at the bottom under "Not implemented" so this
file cannot be mistaken for a larger surface than really exists.

Base URL in production: `https://researchforge.rukon.dev`
Base URL in local development: `http://localhost:8000`

There is **no authentication**. Every endpoint is public. See
[SECURITY](SECURITY.md) for what that means in practice.

---

## GET /

Source: `src/main.py`

Describes the API and points at the docs. Useful as a cheap reachability check
for a human.

**Request:** no parameters.

**Response `200 application/json`**

```json
{
  "message": "ResearchForge API: AI Research Paper Assistant",
  "version": "0.1.0",
  "docs_url": "/docs",
  "health_url": "/health"
}
```

Note that `docs_url` is reported even in production, where the interactive
documentation is disabled. See the next section.

---

## GET /health

Source: `src/main.py`

Liveness check. Called by the frontend on load and by hosting platforms. It is
deliberately fast and touches no external service, so a slow model provider or
an unreachable database can never make the application look down.

**Request:** no parameters.

**Response `200 application/json`**

```json
{
  "status": "ok",
  "app_name": "ResearchForge",
  "version": "0.1.0",
  "environment": "production"
}
```

| Field | Meaning |
| --- | --- |
| `status` | Always `"ok"` when the process is serving. |
| `app_name` | From `APP_NAME`. |
| `version` | The package version in `src/__init__.py`. |
| `environment` | From `APP_ENV`, normally `development` or `production`. |

The frontend renders this as the "Backend online" indicator, including the
version and environment. There is no error response: if the process is not
running, the request fails at the network layer.

---

## POST /api/analyze

Source: `src/api/analyze.py`

Uploads one research paper and returns a complete analysis. This is the only
endpoint that costs money, and the only one that can take minutes.

**Request:** `multipart/form-data`

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `file` | file | yes | The research paper as a PDF. |

The declared `Content-Type` of the part is treated as a hint only. The actual
PDF signature is verified server side, so a mislabelled file is still rejected.

Size limit: `MAX_UPLOAD_SIZE_MB`, default 25 MB. It is checked against the real
byte count, never against a client supplied `Content-Length`.

```bash
curl -X POST https://researchforge.rukon.dev/api/analyze \
  -F "file=@paper.pdf;type=application/pdf"
```

**Response `200 application/json`**

```json
{
  "document": {
    "filename": "paper.pdf",
    "page_count": 15,
    "extracted_characters": 41230,
    "chunk_count": 1,
    "truncated": false
  },
  "summary": {
    "research_problem": "...",
    "methodology": "...",
    "key_findings": ["..."],
    "conclusion": "...",
    "insufficient_evidence": []
  },
  "research_gaps": {
    "stated_limitations": ["..."],
    "identified_gaps": [
      { "gap": "...", "why_it_matters": "...", "evidence": "..." }
    ],
    "insufficient_evidence": false,
    "evidence_note": ""
  },
  "literature_review": {
    "scope_note": "...",
    "major_themes": ["..."],
    "relevant_findings": ["..."],
    "comparisons": ["..."],
    "research_trends": ["..."],
    "limitations": ["..."],
    "future_directions": ["..."],
    "insufficient_evidence": false
  },
  "model_used": "gemini-3.7-flash"
}
```

The exact field list is defined in `src/schemas/analysis.py` and mirrored in
`app/src/lib/api.ts`. The two are kept in step deliberately; a mismatch would
surface in the frontend as a "response in an unexpected shape" error rather
than as silently missing content.

### Honest emptiness

`insufficient_evidence` is not an error path. When a paper genuinely does not
support a section, the model says so there and the frontend prints it. A
position paper with no methodology produces a summary that names `methodology`
in `insufficient_evidence`, not an invented method.

### Error responses

Status codes are chosen so the frontend can distinguish the cases without
parsing message text.

| Status | Meaning | Whose problem |
| --- | --- | --- |
| `413` | File exceeds the upload limit. | The uploader. The message names the limit. |
| `422` | Not a usable PDF: wrong type, empty, encrypted, or scanned with no text layer. | The uploader. |
| `502` | The AI service failed, or returned output that did not match the schema. | The service. Retrying may help. |
| `503` | No AI credentials configured on the server. | An operator. |
| `405` | Wrong method, for example a `GET`. | The caller. |

All errors use FastAPI's standard shape:

```json
{ "detail": "This file is 31.4 MB, which is over the 25 MB limit." }
```

Messages are written for the person reading them and never contain a stack
trace, a file path, an API key, or a raw provider payload. The one exception is
a quota error, where the provider's own text is passed through because it names
which limit was hit and how long to wait, which an operator needs.

---

## Interactive documentation

FastAPI generates OpenAPI documentation at `/docs` and `/redoc`. Both are
**disabled when `APP_ENV=production`**, because they are a development tool and
they enumerate the API surface to anyone who asks.

To read them, run the backend locally and open `http://localhost:8000/docs`.

---

## Not implemented

These endpoints are designed and their request and response models exist in
`src/schemas/library.py`, but **no route is registered for any of them**. They
require a database connection that is not configured. See
[DATABASE](DATABASE.md).

| Planned route | Purpose |
| --- | --- |
| `POST /api/papers` | Save a completed analysis to the library. |
| `GET /api/papers` | List saved papers with search, filter and sort. |
| `GET /api/papers/{id}` | One paper with its most recent analysis. |
| `DELETE /api/papers/{id}` | Remove a paper. |
| `POST /api/reviews/cross` | Generate a literature review across several papers. |
| `GET /api/reviews` | List saved reviews. |
| `GET /api/library/stats` | Real counts for the dashboard. |

Calling any of these today returns `404`.
