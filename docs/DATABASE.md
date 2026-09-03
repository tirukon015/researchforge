# Database

## Status: connected, with per-user isolation enforced by the database

**The database exists, the schema is live, and every row now has an owner.** A
Supabase project is provisioned, migrations 001, 002 and 003 apply, and the
backend reaches PostgREST successfully with the project's secret key present.

Since authentication shipped, **no data request uses the service-role key**.
Reads and writes are made with the signed-in user's own access token, so
Postgres evaluates `auth.uid()` and the Row Level Security policies filter the
query. See [Row Level Security](#row-level-security) below, which is the part of
this document worth reading first.

> **Historical note.** An earlier revision of this file described a production
> outage in which `SUPABASE_SERVICE_ROLE_KEY` held a *publishable* key. A
> publishable key does not bypass RLS, so every `SELECT` returned zero rows and
> the dashboard printed "0 papers" as though it were a measured fact. That key
> has since been replaced with the project's secret key. The guard that
> detected it (`Settings.supabase_key_is_publishable`) is still in place and is
> still tested, because the failure was silent and worth keeping caught.

### What was checked

Verified against the live deployment and its runtime logs, not assumed.

| Check | Result |
| --- | --- |
| `SUPABASE_URL` in Vercel production | Present. A public URL, not a secret |
| `SUPABASE_SERVICE_ROLE_KEY` in Vercel production | Present, holds the project's secret key (was an `sb_publishable_` key; see the historical note above) |
| `SUPABASE_ANON_KEY` in Vercel production | Required since authentication shipped: it is the `apikey` header paired with each user's own token |
| PostgREST reachable from the backend | Yes. `papers`, `analyses` and `literature_reviews` all answer `200 OK` |
| Migrations 001 and 002 applied | Yes. Every table the code queries exists |
| Rows visible to the configured key | None. RLS filters everything for an anonymous key |
| Writes with the configured key | Refused, `401` |
| The same variables in the local environment | Not present. The suite is offline and needs neither |
| Supabase client library installed | No, and deliberately so. PostgREST is called directly over `httpx` |
| Supabase CLI and access token | No CLI on `PATH`, no access token, so the key cannot be rotated from this environment |

### What exists in the repository

| Component | Path | State |
| --- | --- | --- |
| Initial schema | `src/db/migrations/001_initial_schema.sql` | Applied. `papers` and `chunks` exist |
| Analysis and review schema | `src/db/migrations/002_analysis_and_reviews.sql` | Applied. `analyses`, `literature_reviews` and the join table exist |
| Storage independent interface | `src/db/repository.py` | Complete |
| Supabase implementation | `src/db/supabase.py` | Complete. Covered by 40 tests against a mock PostgREST. The embedded-analysis query shape is additionally verified against the live PostgREST instance; the rest is not |
| Request and response models | `src/schemas/library.py` | Complete |
| Settings and detection | `src/config.py`, `Settings.has_database` | Complete. Also rejects a publishable key, see status above |
| Library API routes | `src/api/papers.py`, `src/api/reviews.py` | Wired. 7 endpoints |

The application is therefore complete on this side. Supplying a live project
and its service role key is the only step between here and a working library:
`Settings.has_database` starts returning true, `get_repository` builds the
Supabase implementation, and the 503s become real responses.

## Where session data actually lives

The analysis currently being read is held in React state
(`app/src/lib/session.tsx`) whether or not a database exists. Saved papers come
from the backend; this holder only carries the one in front of you, so it
survives navigation between routes. It is deliberate and documented in that
file:

- It survives navigation between routes within one visit.
- It does **not** survive a reload, a second tab, or a different device.
- It is **not** written to `localStorage`. Durable storage is the database's
  job, and faking it in the browser would break the moment the user opened
  another one.

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

RLS is **enabled on every table**. This is what keeps one researcher's library
out of another's, and since migration 003 it is live rather than dormant.

### How a request is authorised

Every database request the backend makes carries two headers:

| Header | Value | What it does |
|---|---|---|
| `apikey` | the project's **anon** (publishable) key | routes the request to this project. Grants nothing. |
| `Authorization` | **the signed-in user's own access token** | makes Postgres resolve `auth.uid()` to that person |

Because `auth.uid()` resolves to the caller, the policies from migration 002
(`user_id = auth.uid()`) filter every read and every write. A paper belonging
to another account is not hidden by the interface, it is **absent from the
result set**, which is why `GET /api/papers/{someone-elses-id}` answers `404`
and not `403`.

**The service role key is no longer used for any data request.** It bypasses
RLS, so using it would leave isolation resting on the application remembering
to add `WHERE user_id = ...` to every query it will ever contain. One forgotten
filter would return the whole table. Handing PostgREST the caller's own token
instead makes a forgotten filter return *nothing*, which is the failure
direction you want.

### What migration 003 added

- `user_id` now **defaults to `auth.uid()`** on `papers`, `analyses` and
  `literature_reviews`. The owner is decided by Postgres at insert time, from
  who asked, rather than by application code that could have a bug. The
  `WITH CHECK (user_id = auth.uid())` policy refuses the write if the two
  disagree, so the worst case is a failed save and never a paper filed under
  the wrong person.
- A **`RESTRICTIVE`** policy on `literature_review_papers` requiring the linked
  *paper* to be the caller's, not just the review. The `RESTRICTIVE` keyword
  matters: ordinary policies are combined with `OR`, so a second permissive
  policy would have made the table looser. Restrictive ones are combined with
  `AND`.
- A policy on `chunks`, inheriting ownership from the paper. Nothing reads that
  table yet; the policy exists so it is already governed when something does.

### Rows created before authentication

Rows that predate accounts have `user_id = NULL`. In SQL, `NULL = anything` is
`NULL`, which is not `TRUE` - so those rows now match no policy and are
invisible to every account and to the public. **They are not deleted.** They sit
in the database, unmodified and unreachable.

They are deliberately *not* assigned to the first account that registers.
Nobody can prove who uploaded them, and handing one person's uploads to
whoever signs up first is a data-protection failure dressed up as a
convenience. Leaving them unreachable is reversible; guessing is not.

#### Claiming pre-authentication rows

Only the project owner should do this, and only for rows they know are theirs.
Run it in the Supabase SQL Editor **after** creating an account and signing in
once. Find the user id under **Authentication -> Users**.

```sql
-- Replace with YOUR user id from Authentication -> Users.
-- Check first: this shows exactly what would change.
SELECT id, title, filename, created_at
FROM papers
WHERE user_id IS NULL
ORDER BY created_at;

-- Then claim them. Papers, their analyses, and the reviews built from them.
UPDATE papers             SET user_id = 'YOUR-USER-ID' WHERE user_id IS NULL;
UPDATE analyses           SET user_id = 'YOUR-USER-ID' WHERE user_id IS NULL;
UPDATE literature_reviews SET user_id = 'YOUR-USER-ID' WHERE user_id IS NULL;
```

This is kept out of the migration on purpose. A migration runs unattended, and
this decision must not.

### What the tests do and do not prove

`tests/test_ownership.py` proves the application carries each caller's identity
through faithfully, and `tests/test_auth.py` proves every private route refuses
an anonymous request. Neither can exercise Postgres itself - that needs a live
database. The migration's own verification queries (section 6 of
`003_authentication_and_ownership.sql`) are what confirm the policies are
actually in place, and a two-account check against the running deployment is
what confirms the whole chain works end to end.

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
   `002_analysis_and_reviews.sql`, then
   `003_authentication_and_ownership.sql`.
4. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_ANON_KEY` in
   the backend environment, and `NEXT_PUBLIC_SUPABASE_URL` and
   `NEXT_PUBLIC_SUPABASE_ANON_KEY` in the frontend environment. See
   [ENVIRONMENT](ENVIRONMENT.md).
5. In the Supabase dashboard, under **Authentication -> URL Configuration**,
   set the Site URL to the deployment's address and add
   `https://<your-domain>/reset-password` to the redirect allow-list. Without
   it, password-reset links bounce to the wrong place.
6. Redeploy. Environment variables are read at cold start.

### Remaining work after that

Credentials alone are not enough. The following is still required:

- Register the library routes listed in [API](API.md) under "Not implemented".
- Build the repository through a FastAPI dependency, so an unconfigured
  deployment returns a clean `503` instead of failing at import time.
- Add `Save` to the analysis workspace and replace the frontend's in-memory
  session with real fetches.
- Confirm behaviour against a live database. `tests/test_supabase_repository.py`
  asserts the requests this layer builds and the replies it parses, using
  httpx's MockTransport with responses shaped as PostgREST documents them. That
  covers request construction, header handling, error translation, rollback on
  a failed second write, and Content-Range counting. What it cannot prove is
  that the live PostgREST matches its own documentation, so the first real
  connection is still worth watching.
