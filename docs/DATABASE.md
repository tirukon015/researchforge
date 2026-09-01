# Database

## Status: not connected

**ResearchForge is stateless today.** No database is configured, nothing is
persisted, and an analysis is lost when the browser tab is reloaded.

This is a statement about the deployment, not about the code. The schema, the
data access layer and the API contracts are all written. What is missing is a
Supabase project and its credentials.

### What was checked

| Check | Result |
| --- | --- |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` in Vercel production | Not present |
| The same variables in the local environment | Not present |
| Supabase client library installed | No |
| Supabase CLI and access token | No CLI on `PATH`, no access token |
| Tables created anywhere | No project exists to create them in |

### What exists in the repository

| Component | Path | State |
| --- | --- | --- |
| Initial schema | `src/db/migrations/001_initial_schema.sql` | Written, never run |
| Analysis and review schema | `src/db/migrations/002_analysis_and_reviews.sql` | Written, never run |
| Storage independent interface | `src/db/repository.py` | Complete |
| Supabase implementation | `src/db/supabase.py` | Complete, untested against a live database |
| Request and response models | `src/schemas/library.py` | Complete |
| Settings and detection | `src/config.py`, `Settings.has_database` | Complete |
| API routes using any of this | none | **Not wired** |

The last row is the important one. The data layer is not imported by any
endpoint, so connecting credentials alone will not switch the library on. See
"Remaining work" at the end.

## Where session data actually lives

Because there is no database, the frontend keeps the current analysis in React
state (`app/src/lib/session.tsx`). This is deliberate and it is documented in
that file:

- It survives navigation between routes within one visit.
- It does **not** survive a reload, a second tab, or a different device.
- It is **not** written to `localStorage`. Doing so would make "My Papers" look
  like a durable library while nothing is actually stored, and the illusion
  would break the moment the user opened another browser.

The UI states this rather than hiding it.

## Intended schema

Both migration files are additive only. They contain no `DROP`, no `TRUNCATE`,
no `DELETE` and no destructive `ALTER`, and every statement uses
`IF NOT EXISTS`, so re-running either one is safe.

### Provider

Supabase Postgres, with the `vector` extension for embeddings and `pg_trgm` for
substring search.

### Tables

#### `papers` (migration 001, extended by 002)

One row per uploaded research paper.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key, `gen_random_uuid()`. |
| `user_id` | `uuid` | Owner. Null until authentication ships. |
| `title` | `text` | Not null. |
| `authors` | `text[]` | Extracted metadata, not yet populated. |
| `year` | `integer` | Not yet populated. |
| `filename` | `text` | Not null. |
| `storage_path` | `text` | Reference into Supabase Storage. |
| `file_size_bytes` | `bigint` | |
| `page_count` | `integer` | |
| `extracted_characters` | `integer` | Added by 002. |
| `content_type` | `text` | Added by 002. |
| `status` | `text` | `processing`, `ready` or `failed`, enforced by a `CHECK`. |
| `error_message` | `text` | |
| `created_at`, `updated_at` | `timestamptz` | `updated_at` maintained by a trigger. |

#### `chunks` (migration 001)

Searchable pieces of each paper with their embedding vectors. Written for the
retrieval milestone, which is not built.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key. |
| `paper_id` | `uuid` | References `papers(id)` `ON DELETE CASCADE`. |
| `chunk_index` | `integer` | Unique per paper. |
| `content` | `text` | |
| `page_number` | `integer` | Required for citations. |
| `section_title` | `text` | |
| `embedding` | `vector(1024)` | Dimension is permanent. See below. |
| `embedding_model` | `text` | Provenance, so a provider migration is safe. |
| `embedding_dimensions` | `integer` | |

The dimension `1024` is locked. It must match the embedding model, the value
requested from the API, and this column. Changing it means re-embedding every
paper.

#### `analyses` (migration 002)

One completed analysis of one paper.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `uuid` | Primary key. |
| `paper_id` | `uuid` | References `papers(id)` `ON DELETE CASCADE`. |
| `user_id` | `uuid` | Denormalised so a policy can authorise without a join. |
| `model_used` | `text` | Provenance. |
| `summary` | `jsonb` | |
| `research_gaps` | `jsonb` | |
| `literature_review` | `jsonb` | |
| `chunk_count` | `integer` | |
| `truncated` | `boolean` | So a truncated analysis can still say so later. |

The three sections are `jsonb` rather than shredded into columns because they
are read and written whole, and their shape is owned by the Pydantic models in
`src/schemas/analysis.py`. Normalising them would add joins and migrations
without buying a single query the application actually runs.

#### `literature_reviews` and `literature_review_papers` (migration 002)

One table covers both single paper and cross paper reviews, because a cross
paper review is the same object over a larger set of sources.

The join table records **which** papers each review was built from. This is
what lets the interface claim "based on 3 papers" and have that claim be
checkable. Its foreign key to `papers` is `ON DELETE RESTRICT`, deliberately
not cascade: deleting a paper must not silently rewrite a review so it claims
fewer sources than it used.

### Indexes

| Index | Purpose |
| --- | --- |
| `chunks_embedding_hnsw_idx` | Vector similarity search, cosine distance. |
| `chunks_paper_id_idx` | Fetching a paper's chunks and the cascade delete. |
| `papers_created_at_idx` | Library listing, newest first. |
| `papers_status_idx` | Filtering by status. |
| `papers_title_trgm_idx`, `papers_filename_trgm_idx` | Substring search. A plain B-tree cannot serve a leading wildcard. |
| `papers_title_idx` | Sorting by title. |
| `papers_user_id_idx`, `analyses_user_id_idx` | Owner scoped queries. |
| `analyses_paper_id_idx` | Most recent analysis per paper. |

## Row Level Security

RLS is **enabled on every table** with no permissive policy for the anonymous
role. A table with RLS on and no policy is closed. A table with RLS forgotten is
readable by anyone holding the anon key, and that key ships in every browser
bundle.

The backend uses the service role key, which bypasses RLS. That key never
leaves the server.

Migration 002 also creates per user policies (`user_id = auth.uid()`) on
`papers`, `analyses`, `literature_reviews` and the join table. They are inert
today: `auth.uid()` is null for the service role key, and `user_id = NULL` is
never true, so nothing is opened up. When authentication ships, ownership is
already enforced by the database rather than by remembering a `WHERE` clause.

## Storage

Migration 002 creates a **private** bucket named `papers`
(`storage.buckets.public = false`). Uploaded papers are the user's own research
material, and a public bucket would make every stored PDF readable by anyone
who could guess a path.

No file is uploaded to storage today. `POST /api/analyze` reads the PDF into
memory, analyses it, and discards it.

## Enabling the database

1. Create a Supabase project. Use a project dedicated to ResearchForge.
2. Confirm the project host before running anything. Never run these against an
   unrelated project.
3. Open the SQL Editor and run `001_initial_schema.sql`, then
   `002_analysis_and_reviews.sql`.
4. Set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the backend
   environment. See [ENVIRONMENT](ENVIRONMENT.md).
5. Redeploy. Environment variables are read at cold start.

### Remaining work after that

Credentials alone are not enough. The following is still required:

- Register the library routes listed in [API](API.md) under "Not implemented".
- Build the repository through a FastAPI dependency, so an unconfigured
  deployment returns a clean `503` instead of failing at import time.
- Add `Save` to the analysis workspace and replace the frontend's in-memory
  session with real fetches.
- Add integration tests against a live database. `src/db/supabase.py` has never
  run against real Postgres and should not be trusted until it has.
