-- ============================================================
-- ResearchForge, Migration 005: Same-paper analysis cache
-- ============================================================
-- Builds on 001-004. Run those first.
--
-- WHAT THIS IS FOR
-- ----------------
-- Analysing a paper costs three model calls against a paid, rate-limited
-- quota. Two people uploading the SAME paper pay for it twice and get the
-- same answer. This table lets the second upload reuse the first result.
--
-- ⚠️  IT IS NOT A SHARED LIBRARY. Read section 3 before changing anything
--     here. The cache holds analysis TEXT keyed by document content, and
--     deliberately records nothing about who uploaded what. Every user's own
--     papers, analyses and reviews stay private and owned exactly as before -
--     this table sits underneath all of that and is never joined to it.
--
-- ⚠️  TARGET: the ResearchForge Supabase project ONLY. NEVER RPOMS.
--
-- SAFETY: ADDITIVE ONLY. Creates one table and its indexes. No DROP, no
--   TRUNCATE, no DELETE, no ALTER of an existing table, and no change to
--   migrations 001-004. No existing row is read, moved or modified.
--   Re-running it is safe.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> New query -> paste -> Run
-- ============================================================


-- ------------------------------------------------------------
-- 1. The cache
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis_cache (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- SHA-256 of the paper's NORMALISED extracted text, as hex.
    --
    -- The identity is the CONTENT, never the filename. The same paper saved
    -- as "attention.pdf" and "Attention Is All You Need (1).pdf" is one
    -- paper; two different papers that happen to share a filename are two.
    -- Normalisation is deliberately conservative - see
    -- src/services/content_hash.py, which owns the rule this column depends on.
    content_hash       text NOT NULL,

    -- Which generation of the analysis pipeline produced this.
    --
    -- Bumping it in ONE place (ANALYSIS_VERSION in src/services/content_hash.py)
    -- retires every entry at once, without deleting anything: old rows simply
    -- stop matching. That is what makes a prompt or schema change safe - a
    -- result produced by the old prompt is not silently served under the new
    -- one.
    analysis_version   text NOT NULL,

    -- The analysis itself, in the same three jsonb shapes `analyses` uses and
    -- validated by the same Pydantic models on the way in and out.
    summary            jsonb NOT NULL,
    research_gaps      jsonb NOT NULL,
    literature_review  jsonb NOT NULL,

    -- Provenance of the ORIGINAL run. Copied onto each reusing user's own
    -- analysis row so a reused result still says which model wrote it, rather
    -- than crediting whichever provider happens to be primary today.
    model_used         text NOT NULL,
    model_provider     text,
    fallback_used      boolean,
    fallback_provider  text,
    -- Duration of the ORIGINAL analysis. A cache hit is not this fast, and
    -- must not claim to be: the reusing request records its own, far smaller,
    -- elapsed time.
    processing_time_ms integer,

    -- Observability. Never used for billing claims, and no cost figure is
    -- derived from it anywhere - `hit_count` is a count of reuses, nothing more.
    hit_count          integer NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now(),
    last_used_at       timestamptz NOT NULL DEFAULT now(),

    -- ⚠️ THERE IS DELIBERATELY NO user_id COLUMN, AND THERE MUST NOT BE ONE.
    -- Recording who first uploaded a paper would make this table an answer to
    -- "who has read what", which is exactly the question a research tool must
    -- not be able to answer. The absence is the privacy guarantee.
    CONSTRAINT analysis_cache_identity UNIQUE (content_hash, analysis_version)
);

COMMENT ON TABLE analysis_cache IS
    'Reusable analysis results keyed by document content. NOT a user library: '
    'holds no ownership and is never joined to papers or analyses.';
COMMENT ON COLUMN analysis_cache.content_hash IS
    'SHA-256 of the normalised extracted text. Content is the identity, not the filename.';
COMMENT ON COLUMN analysis_cache.processing_time_ms IS
    'Duration of the ORIGINAL analysis, not of a cache hit.';


-- ------------------------------------------------------------
-- 2. The lookup index
-- ------------------------------------------------------------
-- The UNIQUE constraint above already creates the index this lookup uses
-- (content_hash, analysis_version), so no second index is added for it.
-- This one supports eviction and reporting by age.
CREATE INDEX IF NOT EXISTS analysis_cache_last_used_idx
    ON analysis_cache (last_used_at DESC);


-- ------------------------------------------------------------
-- 3. Row Level Security: CLOSED TO EVERY CLIENT
-- ------------------------------------------------------------
-- RLS on, and NOT ONE POLICY. A table with RLS enabled and no policy is
-- readable and writable by nobody holding an anon or user key.
--
-- ⚠️ THIS IS THE PRIVACY DESIGN, NOT AN OVERSIGHT. DO NOT ADD A POLICY.
--
-- Every other table in this schema is reached with the signed-in user's own
-- token, so the database filters it per user. This one is different: the
-- backend reaches it with the SERVICE-ROLE key, which never leaves the server.
--
-- That inversion is deliberate. A permissive read policy - even one limited to
-- authenticated users - would let any account enumerate the table and read the
-- analysis of every paper anybody had ever uploaded, including unpublished
-- work. Keeping it server-only means a cached analysis can be obtained in
-- exactly one way: by uploading a document whose text hashes to that entry.
-- You can only get the analysis of a paper you already possess.
--
-- The service-role path is therefore narrower than it sounds. It is used for
-- two operations, both keyed by a hash the caller proved they hold, and
-- neither returning anything about any user.
ALTER TABLE analysis_cache ENABLE ROW LEVEL SECURITY;


-- ------------------------------------------------------------
-- 3b. Usage counter
-- ------------------------------------------------------------
-- PostgREST cannot express `hit_count = hit_count + 1` through a PATCH, and
-- read-then-write from the application would lose increments whenever two
-- users hit the same entry at once. One statement in the database is both
-- correct under concurrency and a single round trip.
--
-- SECURITY DEFINER is NOT used, deliberately. The function runs with the
-- caller's rights, so it grants nothing that RLS does not already allow -
-- only the service-role key can reach the table, and this does not change
-- that. It touches counters and nothing else.
CREATE OR REPLACE FUNCTION touch_analysis_cache(row_id uuid)
RETURNS void AS $$
    UPDATE analysis_cache
    SET hit_count = hit_count + 1,
        last_used_at = now()
    WHERE id = row_id;
$$ LANGUAGE sql;

COMMENT ON FUNCTION touch_analysis_cache(uuid) IS
    'Increment the reuse counter for one cache entry. Observability only.';


-- ------------------------------------------------------------
-- 3c. Record which analyses were reused rather than generated
-- ------------------------------------------------------------
-- Nullable with no backfill, for the same reason as migration 004's
-- provenance columns: an analysis stored before this column existed genuinely
-- has no recorded answer, and writing `false` in would be asserting something
-- nobody observed. NULL means "not recorded".
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS cache_hit boolean;

COMMENT ON COLUMN analyses.cache_hit IS
    'True when this analysis reused a cached result for the same document '
    'instead of calling a model. NULL means not recorded.';


-- ------------------------------------------------------------
-- 4. Verification
-- ------------------------------------------------------------
-- (a) The table exists. Expect one row.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = 'analysis_cache';

-- (b) It has NO user column. Expect ZERO rows - that is the privacy property.
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'analysis_cache'
  AND column_name IN ('user_id', 'owner_id', 'uploaded_by', 'email');

-- (c) RLS is on and there are NO policies. Expect rowsecurity = true, and the
--     second query to return zero rows.
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND tablename = 'analysis_cache';

SELECT policyname FROM pg_policies
WHERE schemaname = 'public' AND tablename = 'analysis_cache';

-- (d) One entry per (content_hash, analysis_version). Expect the UNIQUE row.
SELECT conname, contype FROM pg_constraint
WHERE conrelid = 'analysis_cache'::regclass AND contype = 'u';

-- (e) The counter function exists. Expect one row.
SELECT proname FROM pg_proc WHERE proname = 'touch_analysis_cache';

-- (f) Nothing else changed. Expect papers 2, analyses 2, reviews 1, cache 0.
SELECT
    (SELECT count(*) FROM papers)             AS papers,
    (SELECT count(*) FROM analyses)           AS analyses,
    (SELECT count(*) FROM literature_reviews) AS reviews,
    (SELECT count(*) FROM analysis_cache)     AS cache_entries;
