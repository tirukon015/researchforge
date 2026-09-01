# API reference

Every endpoint below was read from the source. The backend exposes **12
operations across 9 paths**: three for system and analysis, nine for the
research library.

The library routes are registered and complete, but they need durable storage.
While no database is configured they answer `503` with a message saying the
library is not connected. That is deliberate: an empty list would be a claim
("you have no papers") that a deployment with nowhere to store papers cannot
make.

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
  "environment": "production",
  "library": false
}
```

| Field | Meaning |
| --- | --- |
| `status` | Always `"ok"` when the process is serving. |
| `app_name` | From `APP_NAME`. |
| `version` | The package version in `src/__init__.py`. |
| `environment` | From `APP_ENV`, normally `development` or `production`. |
| `library` | Whether durable storage is configured. A boolean, never the URL and never the key. |

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

## Library routes

All nine require durable storage. Without it every one returns `503`; the
message names the situation rather than pretending the library is empty.

Full request and response models are in `src/schemas/library.py`.

### POST /api/papers

Save a completed analysis. The analysis is sent by the client rather than
re-run: it has already been paid for, and re-generating on save could store a
different answer than the one the user chose to keep.

Body: `title`, `filename`, `file_size_bytes`, `content_type`, plus the
`document`, `summary`, `research_gaps`, `literature_review` and `model_used`
from the analysis response. Unknown fields are rejected with `422`.

Returns `201` and the stored `PaperDetail`.

### GET /api/papers

List the library.

| Query | Default | Notes |
| --- | --- | --- |
| `search` | none | Matches title or filename, case insensitive substring. |
| `status` | all | `ready`, `processing` or `failed`. |
| `sort` | `newest` | `newest`, `oldest` or `title`. |
| `limit` | 50 | 1 to 100. |
| `offset` | 0 | |

Returns `{ "papers": [...], "total": n }`. `total` counts every match before
paging, so the interface can say "12 of 40" without under reporting.

### GET /api/papers/stats

Counts for the dashboard, derived from stored rows. Nothing is estimated.

### GET /api/papers/{id}

One paper with its most recent analysis. `404` when it is not in the library.

### DELETE /api/papers/{id}

Removes a paper and its analyses. `404` when absent.

Returns **`409`** when a saved literature review was generated from it.
Cascading the delete would leave that review claiming more sources than it can
still name, which is a quieter and worse failure than refusing.

### POST /api/reviews/cross

Generate one literature review across several saved papers.

Body: `paper_ids` (2 to 12) and an optional `title`. Fewer than two is rejected
with `422`, because a cross paper review of one paper is that paper's own
review, which already exists.

`404` if **any** selected paper is missing. A review that silently covered four
of five would still be reported as five.

`422` if any selected paper has no stored analysis.

Reviews read the stored analyses rather than re-reading the PDFs. A dozen full
papers overrun the context window, and the analysis has already been paid for
once. The limitation is real: such a review cannot surface something the
original analysis missed.

Returns `201` and the review, including the papers it was built from, named so
the "based on N papers" claim can be checked.

### GET /api/reviews, GET /api/reviews/{id}, DELETE /api/reviews/{id}

List, fetch and delete saved reviews. `404` when absent.

---

## Not implemented

| Planned | Status |
| --- | --- |
| Authentication | No accounts. Every endpoint is public. |
| PDF file storage | The private bucket is defined in migration 002; nothing writes to it. |
| Retrieval over a corpus | The embedding provider builds requests but makes no network call. |
| Rate limiting | `RATE_LIMIT_PER_MINUTE` is in `.env.example` and nothing reads it. |
