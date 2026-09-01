-- ============================================================
-- ResearchForge, Migration 002: Analyses and literature reviews
-- ============================================================
-- Builds on 001 (papers, chunks). Adds the tables that make the
-- research library durable: the structured analysis produced for a
-- paper, and the literature reviews written across one or more papers.
--
-- ⚠️  TARGET: the ResearchForge Supabase project ONLY.
--     Before running this, confirm the SUPABASE_URL host matches the
--     ResearchForge project. NEVER run against RPOMS.
--
-- SAFETY: ADDITIVE ONLY. No DROP, no TRUNCATE, no DELETE, no
--   destructive ALTER. Every statement uses IF NOT EXISTS, so
--   re-running it is safe and produces no error.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> New query
--   -> paste this whole file -> Run
--   (Run 001_initial_schema.sql first if you have not already.)
-- ============================================================


-- ------------------------------------------------------------
-- 1. Columns 001 could not know about
-- ------------------------------------------------------------
-- 001 was written before the analysis pipeline existed. These are the
-- two facts the library list needs but that table cannot yet hold.
-- ADD COLUMN IF NOT EXISTS is additive and safe on a populated table.
ALTER TABLE papers ADD COLUMN IF NOT EXISTS extracted_characters integer;
ALTER TABLE papers ADD COLUMN IF NOT EXISTS content_type text;


-- ------------------------------------------------------------
-- 2. analyses: one completed analysis of one paper
-- ------------------------------------------------------------
-- The three analysis sections are stored as jsonb rather than being
-- shredded into columns. They are read and written whole, they are
-- validated on the way in by the Pydantic models in
-- src/schemas/analysis.py, and their shape is owned by the model
-- contract - so normalising them into tables would add joins and
-- migrations without buying a single query we actually run.
--
-- jsonb (not json) because it is the binary form: it deduplicates keys,
-- and it is the only one of the two that can be indexed.
CREATE TABLE IF NOT EXISTS analyses (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- ON DELETE CASCADE: deleting a paper deletes its analyses. An
    -- analysis without its paper is unreadable - it has no title, no
    -- filename, and no source to be grounded in.
    paper_id       uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,

    -- Denormalised owner. Copied from papers.user_id so a row-level
    -- security policy can authorise this table without a join back to
    -- papers on every single read.
    user_id        uuid,

    -- Provenance: which model produced this, so an output can always be
    -- traced to the thing that wrote it (same argument as
    -- chunks.embedding_model in 001).
    model_used     text NOT NULL,

    summary            jsonb NOT NULL,
    research_gaps      jsonb NOT NULL,
    literature_review  jsonb NOT NULL,

    -- How the paper was read, kept for honesty in the UI: a truncated
    -- analysis must be able to say so long after the request is gone.
    chunk_count    integer NOT NULL DEFAULT 1,
    truncated      boolean NOT NULL DEFAULT false,

    created_at     timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  analyses IS 'One completed analysis of one paper.';
COMMENT ON COLUMN analyses.model_used IS
    'Model that produced this analysis. Provenance - do not drop.';
COMMENT ON COLUMN analyses.truncated IS
    'True if the paper exceeded the analysis window and content was dropped.';

-- The library list shows each paper with its most recent analysis.
CREATE INDEX IF NOT EXISTS analyses_paper_id_idx
    ON analyses (paper_id, created_at DESC);
CREATE INDEX IF NOT EXISTS analyses_user_id_idx ON analyses (user_id);


-- ------------------------------------------------------------
-- 3. literature_reviews: single-paper and cross-paper reviews
-- ------------------------------------------------------------
-- One table covers both kinds. A cross-paper review is not a different
-- object from a single-paper one; it is the same object over a larger
-- set of sources, so splitting them would duplicate every column and
-- every query for no gain.
CREATE TABLE IF NOT EXISTS literature_reviews (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid,

    title        text NOT NULL,
    model_used   text NOT NULL,

    -- The review body, matching the LiteratureReview schema.
    content      jsonb NOT NULL,

    -- Denormalised count of contributing papers. The UI states "based
    -- on N papers" on every card; without this the list page would need
    -- a correlated subquery per row to render honestly.
    paper_count  integer NOT NULL DEFAULT 0,

    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE literature_reviews IS
    'A literature review over one or more papers.';
COMMENT ON COLUMN literature_reviews.paper_count IS
    'Number of contributing papers. The UI claims this figure - keep it true.';

CREATE INDEX IF NOT EXISTS literature_reviews_created_at_idx
    ON literature_reviews (created_at DESC);
CREATE INDEX IF NOT EXISTS literature_reviews_user_id_idx
    ON literature_reviews (user_id);


-- ------------------------------------------------------------
-- 4. literature_review_papers: which papers a review was built from
-- ------------------------------------------------------------
-- The join table is what lets the product prove its own claim. The UI
-- says "Based on 3 selected papers"; this is the record of WHICH three,
-- so that statement can be verified rather than trusted.
CREATE TABLE IF NOT EXISTS literature_review_papers (
    review_id  uuid NOT NULL
               REFERENCES literature_reviews(id) ON DELETE CASCADE,

    -- RESTRICT, deliberately NOT cascade. Deleting a paper that a review
    -- was built from must not silently rewrite history so the review
    -- claims fewer sources than it actually used. The application
    -- detaches the review explicitly, or the delete is refused.
    paper_id   uuid NOT NULL
               REFERENCES papers(id) ON DELETE RESTRICT,

    -- Preserves the order the user selected the papers in.
    position   integer NOT NULL DEFAULT 0,

    PRIMARY KEY (review_id, paper_id)
);

COMMENT ON TABLE literature_review_papers IS
    'Which papers each literature review was generated from.';

CREATE INDEX IF NOT EXISTS literature_review_papers_paper_idx
    ON literature_review_papers (paper_id);


-- ------------------------------------------------------------
-- 5. Search support
-- ------------------------------------------------------------
-- The library searches title and filename. pg_trgm makes a case-
-- insensitive substring match (ILIKE '%term%') use an index instead of
-- scanning every row - a plain B-tree cannot help a leading wildcard.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS papers_title_trgm_idx
    ON papers USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS papers_filename_trgm_idx
    ON papers USING gin (filename gin_trgm_ops);

-- Sorting by title is offered in the library toolbar.
CREATE INDEX IF NOT EXISTS papers_title_idx ON papers (title);

-- Every list query is scoped to the owner once authentication ships.
CREATE INDEX IF NOT EXISTS papers_user_id_idx ON papers (user_id);


-- ------------------------------------------------------------
-- 6. Keep updated_at accurate automatically
-- ------------------------------------------------------------
-- Reuses set_updated_at() defined in 001.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'literature_reviews_set_updated_at'
    ) THEN
        CREATE TRIGGER literature_reviews_set_updated_at
            BEFORE UPDATE ON literature_reviews
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;


-- ------------------------------------------------------------
-- 7. Row Level Security
-- ------------------------------------------------------------
-- Same posture as 001: RLS ON with no permissive policy, so the public
-- `anon` key can read nothing at all. The backend holds the service-role
-- key, which bypasses RLS, and that key never leaves the server.
--
-- This is the safe default. A table with RLS enabled and no policy is
-- closed; a table with RLS forgotten is world-readable to anyone holding
-- the anon key, which ships in every browser bundle.
ALTER TABLE analyses                ENABLE ROW LEVEL SECURITY;
ALTER TABLE literature_reviews      ENABLE ROW LEVEL SECURITY;
ALTER TABLE literature_review_papers ENABLE ROW LEVEL SECURITY;


-- ------------------------------------------------------------
-- 8. Per-user policies, ready for authentication (feature E5)
-- ------------------------------------------------------------
-- These are created now but are inert until rows carry a user_id and
-- requests arrive with a Supabase JWT: auth.uid() is NULL for the
-- service-role key, and `user_id = NULL` is never true, so nothing is
-- opened up today. When authentication ships, ownership is already
-- enforced by the database rather than by remembering a WHERE clause.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'papers' AND policyname = 'papers_owner_all'
    ) THEN
        CREATE POLICY papers_owner_all ON papers
            FOR ALL USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'analyses' AND policyname = 'analyses_owner_all'
    ) THEN
        CREATE POLICY analyses_owner_all ON analyses
            FOR ALL USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid());
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'literature_reviews'
          AND policyname = 'literature_reviews_owner_all'
    ) THEN
        CREATE POLICY literature_reviews_owner_all ON literature_reviews
            FOR ALL USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid());
    END IF;

    -- The join table has no user_id of its own; ownership is inherited
    -- from the review it belongs to.
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'literature_review_papers'
          AND policyname = 'literature_review_papers_owner_all'
    ) THEN
        CREATE POLICY literature_review_papers_owner_all
            ON literature_review_papers
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM literature_reviews r
                    WHERE r.id = literature_review_papers.review_id
                      AND r.user_id = auth.uid()
                )
            );
    END IF;
END $$;


-- ------------------------------------------------------------
-- 9. Storage bucket for uploaded PDFs
-- ------------------------------------------------------------
-- PRIVATE bucket (public = false). Uploaded papers are the user's own
-- research material; a public bucket would make every stored PDF
-- readable by anyone who can guess a path. The backend reads them with
-- the service-role key and issues short-lived signed URLs when a file
-- genuinely needs to reach the browser.
INSERT INTO storage.buckets (id, name, public)
VALUES ('papers', 'papers', false)
ON CONFLICT (id) DO NOTHING;


-- ------------------------------------------------------------
-- 10. Verification
-- ------------------------------------------------------------
-- After running, this should return:
--   analyses, chunks, literature_review_papers, literature_reviews, papers
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
      'papers', 'chunks', 'analyses',
      'literature_reviews', 'literature_review_papers'
  )
ORDER BY table_name;
