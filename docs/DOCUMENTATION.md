# ResearchForge documentation

The main reference. It explains the complete lifecycle of a request and what
each subsystem is responsible for. For narrower topics see
[ARCHITECTURE](ARCHITECTURE.md), [API](API.md), [DATABASE](DATABASE.md),
[SETUP](SETUP.md), [DEPLOYMENT](DEPLOYMENT.md),
[ENVIRONMENT](ENVIRONMENT.md), [SECURITY](SECURITY.md),
[TROUBLESHOOTING](TROUBLESHOOTING.md) and
[PROJECT_STRUCTURE](PROJECT_STRUCTURE.md).

## What ResearchForge is

An AI research paper assistant. A user uploads an academic PDF and receives
three things: a structured summary, an analysis of the research gaps the paper
leaves open, and a literature review of the prior work the paper itself
discusses.

The governing principle is that **every claim is grounded in the uploaded
paper**. Where the paper does not support a section, the system says so rather
than filling the space with something plausible.

## The complete lifecycle

```
User selects a PDF in the browser
        |
        v
Frontend validates type, emptiness and size
        |
        v  multipart/form-data POST /api/analyze
FastAPI reads the body, checks the real byte count
        |
        v
pypdf verifies the PDF signature and extracts text
        |
        +--> no text layer, encrypted, or empty  --> 422, stop
        |
        v
Is the text longer than 400,000 characters?
        |
        +-- no --> analyse the paper whole
        |
        +-- yes -> split into chunks, digest each one, concatenate
        |
        v
Three separate model calls, each schema constrained
        |
        +--> 1. Summary
        +--> 2. Research gaps
        +--> 3. Literature review
        |
        v
Each response validated against its Pydantic model
        |
        +--> refusal, truncation, or schema mismatch --> 502, stop
        |
        v
One JSON response assembled and returned
        |
        v
Frontend stores it in React state and renders the workspace
        |
        v
[ persistence would go here, and does not exist yet ]
```

## Subsystems

### Frontend

Next.js 16 App Router, React 19, TypeScript in strict mode, plain CSS with no
framework.

Responsibilities:

- Present the four routes and the analysis workspace.
- Validate a file before uploading it, as a courtesy.
- Call the backend, and only from `app/src/lib/api.ts`.
- Translate failures into wording the user can act on.
- Hold the current analysis in memory for the duration of the visit.

It deliberately does **not** decide anything about the analysis. It renders
what the backend returned, and where a section is marked as unsupported it
prints that rather than an empty box.

### Backend

FastAPI on Python 3.12 or newer.

Responsibilities:

- Accept and validate the upload against real bytes, not client claims.
- Extract text from the PDF.
- Decide whether the paper needs chunking.
- Run the three analysis calls through the provider abstraction.
- Map every failure onto a status code the frontend can distinguish.

`src/main.py` is a wiring file. Decisions live in `src/services/analysis.py`,
and vendor code is confined to provider modules.

### AI provider

`src/rag/llm/base.py` defines the contract. Two implementations exist: Google
Gemini (the default, `gemini-3.7-flash`) and Anthropic. `LLM_PROVIDER` selects
one at runtime.

Responsibilities:

- Constrain the model to the requested JSON schema.
- Validate the reply again on return, because a schema constrains the model but
  does not guarantee the answer.
- Reject a truncated reply. This is the dangerous failure: it arrives as a
  success with content missing.
- Translate vendor exceptions into project owned errors so a rejected key stays
  distinguishable from a network fault.

The prompts live in `src/prompts/analysis.py` and are versioned, currently
`1.1.0`. The shared system prompt carries the anti fabrication contract, the
instruction that the paper is data rather than instructions, and a punctuation
rule that keeps decorative dashes out of generated text.

### File handling

The PDF is read into memory, analysed and discarded. It is never written to
disk and never stored. The filename is display text and is never used to build
a path.

### Database

**Not connected.** The schema, the repository interface, a Supabase
implementation and the request models all exist, but no endpoint imports them.
See [DATABASE](DATABASE.md) for the full status.

### API communication

One JSON contract, defined twice and kept in step: `src/schemas/analysis.py` on
the server, `app/src/lib/api.ts` in the browser. Drift is detected at runtime
by a shape check, so a mismatch produces a clear error rather than blank
sections.

### Error handling

Failures are classified rather than described. The backend picks a status code
and the frontend picks wording from it.

| Kind | Status | What the user is told |
| --- | --- | --- |
| `offline` | network failure | The backend did not respond. |
| `rejected` | 413, 422, 415 | Choose a different file. |
| `upstream` | 502 and other 5xx | The AI service failed, not your file. |
| `config` | 503 | An administrator must fix the deployment. |
| `malformed` | 200 with a bad shape | The two sides may be running different versions. |

### Deployment

One Vercel project running two services behind one origin. The Vercel project
is not linked to GitHub, so production is updated with `vercel deploy --prod`.
See [DEPLOYMENT](DEPLOYMENT.md).

## Feature status

### Implemented

- PDF upload with drag and drop, file picker, size and type validation
- Text extraction with pypdf, including rejection of scanned and encrypted files
- Automatic chunking for papers over 400,000 characters
- Structured summary: research problem, methodology, key findings, conclusion
- Research gap analysis, each gap carrying the evidence it rests on
- Single paper literature review
- Tabbed analysis workspace with copy actions
- Dashboard with session scoped counts
- Health monitoring through `GET /health` and a live indicator
- Provider abstraction with Gemini and Anthropic implementations
- Honest empty, loading and error states throughout
- Light and dark themes following the operating system preference
- Responsive layout with a mobile navigation drawer
- Custom domain serving the production application
- 114 offline tests, lint and type checking

### Partially implemented

| Feature | What exists | What is missing |
| --- | --- | --- |
| My Papers | The page, the card layout, an empty state | Any stored papers |
| Literature review | Single paper reviews | Cross paper reviews |
| Database layer | Migrations, repository, Supabase client, schemas | A database, and any endpoint that uses them |
| Embeddings | Provider interface, request construction, tests | The network call and any retrieval |

### Not implemented

- Persistent storage of any kind
- Authentication and user accounts
- Saved history across sessions
- Search, filtering and sorting of a library
- Cross paper analysis
- Multi paper selection and a research workspace
- File storage for uploaded PDFs
- Rate limiting
- A theme toggle. Themes follow the system setting and cannot be overridden in
  the interface.

### Planned

- Retrieval augmented generation over a stored corpus, using Jina
  `jina-embeddings-v3` at 1024 dimensions with pgvector
- Cross paper literature review built on that retrieval
- Bibliographic metadata extraction, so a paper is listed by title and authors
  rather than by filename

## Known limitations

1. **Nothing is saved.** Reloading the tab discards the analysis.
2. **The free AI tier is small.** One analysis costs three provider requests.
3. **No OCR.** A scanned paper has no text layer and is rejected.
4. **Single paper scope.** The literature review reads one paper's own related
   work. It does not search a corpus, and the interface says so.
5. **No rate limiting.** The analysis endpoint is public and costs money per
   call.
6. **The database layer is untested against a real database.** It should not be
   trusted until it has run against live Postgres.
