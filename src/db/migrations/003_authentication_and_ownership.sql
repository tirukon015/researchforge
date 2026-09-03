-- ============================================================
-- ResearchForge, Migration 003: Authentication and ownership
-- ============================================================
-- Builds on 001 (papers, chunks) and 002 (analyses, reviews, RLS policies).
--
-- WHAT THIS FIXES
-- ---------------
-- Before this migration the API read the library with the SERVICE-ROLE key,
-- which bypasses Row Level Security. There was one library and everybody saw
-- it: User A uploaded a paper and User B, on another device, could open it.
--
-- 002 already created the right policies (`user_id = auth.uid()`). They were
-- inert for two reasons, and this migration removes both:
--
--   1. Requests arrived with a key that bypasses RLS, so no policy ran.
--      FIXED IN CODE, not here: src/db/supabase.py now sends the signed-in
--      user's own access token, so Postgres evaluates auth.uid() as them.
--   2. Nothing set `user_id` on insert, so even a correctly-authenticated
--      write would have been REFUSED by the WITH CHECK clause.
--      FIXED HERE: the column now defaults to auth.uid().
--
-- ⚠️  TARGET: the ResearchForge Supabase project ONLY.
--     Before running this, confirm the SUPABASE_URL host matches the
--     ResearchForge project. NEVER run against RPOMS.
--
-- SAFETY: ADDITIVE ONLY. No DROP, no TRUNCATE, no DELETE, no destructive
--   ALTER. It adds column DEFAULTs, adds policies, and adds indexes. No
--   existing row is modified, moved, reassigned, or removed. Re-running it
--   is safe.
--
-- ⚠️  EXISTING ROWS ARE DELIBERATELY LEFT ALONE. See section 5.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> New query
--   -> paste this whole file -> Run
--   (Run 001 and 002 first if you have not already.)
-- ============================================================


-- ------------------------------------------------------------
-- 1. The owner is filled in by the DATABASE, not by the application
-- ------------------------------------------------------------
-- `auth.uid()` is the Supabase function that returns the id of the user whose
-- JWT was sent with the request (NULL when there is no user). Making it the
-- column DEFAULT means a row's owner is decided by WHO ASKED, at the moment of
-- the insert, in Postgres.
--
-- Why that matters more than it looks: the application also sends `user_id`
-- explicitly, but an application can have a bug. A DEFAULT cannot be given the
-- wrong value by forgetting a line, and the `WITH CHECK (user_id = auth.uid())`
-- policy from 002 rejects the write outright if the two ever disagree. The
-- worst case becomes a refused save, never a paper filed under the wrong person.
--
-- ALTER COLUMN ... SET DEFAULT changes only what happens to FUTURE inserts.
-- It does not touch a single existing row.
ALTER TABLE papers             ALTER COLUMN user_id SET DEFAULT auth.uid();
ALTER TABLE analyses           ALTER COLUMN user_id SET DEFAULT auth.uid();
ALTER TABLE literature_reviews ALTER COLUMN user_id SET DEFAULT auth.uid();


-- ------------------------------------------------------------
-- 2. The join table must check BOTH ends
-- ------------------------------------------------------------
-- 002's policy on literature_review_papers checked only that the REVIEW
-- belonged to the caller. That leaves a gap: a user could, in principle, link
-- somebody else's paper_id into their own review, and the review would then
-- name a source its author cannot read.
--
-- In practice RLS on `papers` already stops this one step earlier - another
-- user's paper is invisible, so the API's "are all these papers still here?"
-- check fails first with a plain not-found. This closes it at the database
-- anyway, because "some other layer happens to catch it" is not the same
-- guarantee as "the database will not store it".
--
-- ⚠️  IT IS DECLARED `AS RESTRICTIVE`, AND THAT KEYWORD IS THE WHOLE POINT.
-- Postgres combines ordinary (PERMISSIVE) policies with **OR**: adding a
-- second permissive policy beside 002's would make the table LOOSER, granting
-- access to anyone either policy allows - the exact opposite of the intent.
-- A RESTRICTIVE policy is combined with **AND** instead, so a row must satisfy
-- 002's rule (the review is mine) *and* this one (the paper is mine).
--
-- CREATE POLICY has no IF NOT EXISTS, so it is guarded by a catalogue lookup
-- the way 002 does it. 002's policy is left in place, unmodified; nothing is
-- dropped.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename  = 'literature_review_papers'
          AND policyname = 'literature_review_papers_paper_owner'
    ) THEN
        CREATE POLICY literature_review_papers_paper_owner
            ON literature_review_papers
            AS RESTRICTIVE
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM papers p
                    WHERE p.id = literature_review_papers.paper_id
                      AND p.user_id = auth.uid()
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM papers p
                    WHERE p.id = literature_review_papers.paper_id
                      AND p.user_id = auth.uid()
                )
            );
    END IF;
END $$;


-- ------------------------------------------------------------
-- 3. chunks: ownership inherited from the paper
-- ------------------------------------------------------------
-- `chunks` has RLS enabled (001) and NO policy, which means it is closed to
-- everyone - correct today, because nothing reads or writes it: embeddings and
-- retrieval are not built (see CLAUDE.md §14). A policy is added now so that
-- when they are, the table is already governed by the same rule as everything
-- else, rather than being opened in a hurry by whoever needs it first.
--
-- chunks has no user_id of its own and should not gain one: a chunk belongs to
-- a paper, and a second copy of the owner is a second thing that can drift out
-- of step with the first.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'chunks' AND policyname = 'chunks_owner_all'
    ) THEN
        CREATE POLICY chunks_owner_all ON chunks
            FOR ALL USING (
                EXISTS (
                    SELECT 1 FROM papers p
                    WHERE p.id = chunks.paper_id
                      AND p.user_id = auth.uid()
                )
            )
            WITH CHECK (
                EXISTS (
                    SELECT 1 FROM papers p
                    WHERE p.id = chunks.paper_id
                      AND p.user_id = auth.uid()
                )
            );
    END IF;
END $$;


-- ------------------------------------------------------------
-- 4. Indexes that the policies now depend on
-- ------------------------------------------------------------
-- Every read of `papers` now carries `user_id = auth.uid()`. 002 already
-- indexed papers.user_id and analyses.user_id; the composite below is what
-- keeps the default library listing (this user's papers, newest first) a
-- single index scan instead of a filter over everything the user owns.
CREATE INDEX IF NOT EXISTS papers_user_created_idx
    ON papers (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS literature_reviews_user_created_idx
    ON literature_reviews (user_id, created_at DESC);


-- ------------------------------------------------------------
-- 5. EXISTING ROWS: preserved, not reassigned
-- ------------------------------------------------------------
-- ⚠️  READ THIS BEFORE WONDERING WHERE THE OLD PAPERS WENT.
--
-- Rows created before authentication existed have `user_id = NULL`. This
-- migration does NOT delete them and does NOT give them an owner.
--
-- What happens to them: `user_id = auth.uid()` is never true when user_id is
-- NULL (in SQL, NULL = anything is NULL, which is not TRUE). So those rows
-- become invisible to every signed-in user, and to the anonymous public. They
-- are still in the database, whole and unmodified.
--
-- Why they are not simply assigned to the first account that appears: nobody
-- can prove who uploaded them. Handing one person's uploads to whoever
-- registers first is a data-protection failure dressed up as a convenience,
-- and it cannot be undone once the audit trail is gone. Leaving them
-- unreachable is reversible; guessing is not.
--
-- TO CLAIM THEM LATER, deliberately: create your account, sign in, find your
-- user id in Supabase (Dashboard -> Authentication -> Users), and run the
-- statement in docs/DATABASE.md under "Claiming pre-authentication rows".
-- It is kept out of this file on purpose - a migration runs unattended, and
-- this decision must not.


-- ------------------------------------------------------------
-- 6. Verification
-- ------------------------------------------------------------
-- (a) Every user-owned table should now default user_id to auth.uid().
--     Expect three rows, each with column_default = 'auth.uid()'.
SELECT table_name, column_name, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name  = 'user_id'
  AND table_name IN ('papers', 'analyses', 'literature_reviews')
ORDER BY table_name;

-- (b) RLS must be ON for all five tables. Expect rowsecurity = true for each.
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
      'papers', 'chunks', 'analyses',
      'literature_reviews', 'literature_review_papers'
  )
ORDER BY tablename;

-- (c) The policies that enforce ownership. Expect six:
--     papers_owner_all, analyses_owner_all, literature_reviews_owner_all,
--     literature_review_papers_owner_all, literature_review_papers_paper_owner,
--     chunks_owner_all
--
--     `permissive` must read RESTRICTIVE for literature_review_papers_paper_owner
--     and PERMISSIVE for the rest. A PERMISSIVE row there would mean the
--     policy is OR-ed in and grants access instead of narrowing it.
SELECT tablename, policyname, permissive, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- (d) How many rows predate authentication and are therefore now unreachable.
--     This is a COUNT, not a change. If it is not zero, section 5 explains why
--     and docs/DATABASE.md explains how to claim them.
SELECT
    (SELECT count(*) FROM papers             WHERE user_id IS NULL) AS papers_without_owner,
    (SELECT count(*) FROM analyses           WHERE user_id IS NULL) AS analyses_without_owner,
    (SELECT count(*) FROM literature_reviews WHERE user_id IS NULL) AS reviews_without_owner;
