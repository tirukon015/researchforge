-- ============================================================
-- ResearchForge, Migration 004: Owner role, AI configuration, analysis metadata
-- ============================================================
-- Builds on 001, 002 and 003. Run those first.
--
-- WHAT THIS ADDS
-- --------------
--   1. `app_owners`      who may change global settings
--   2. `system_settings` global configuration, currently one row:
--                        which AI provider is primary
--   3. columns on `analyses` recording WHICH model actually produced each
--      result, and whether the fallback was used
--
-- ⚠️  TARGET: the ResearchForge Supabase project ONLY.
--     Confirm the SUPABASE_URL host matches ResearchForge. NEVER run against
--     RPOMS.
--
-- SAFETY: ADDITIVE ONLY. No DROP, no TRUNCATE, no DELETE, no destructive
--   ALTER. Every statement is IF NOT EXISTS or ADD COLUMN IF NOT EXISTS, so
--   re-running it is safe and changes nothing the second time.
--
-- ⚠️  EXISTING ROWS ARE NOT MODIFIED. The new columns on `analyses` are
--     NULLABLE with no backfill, deliberately: a historical analysis was
--     produced before this metadata was recorded, and inventing a value for it
--     would be fabricating provenance. NULL means "not recorded", which is the
--     truth. See section 3.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> New query -> paste -> Run
-- ============================================================


-- ------------------------------------------------------------
-- 1. app_owners: who may change global configuration
-- ------------------------------------------------------------
-- A TABLE rather than a column on a profile, and rather than an email compared
-- in application code, for three reasons:
--
--   * The database can check it. That means the RLS policy in section 2 is a
--     real boundary, not a reminder to the backend to remember a check.
--   * Ownership is data, so granting and revoking it is an INSERT and a DELETE
--     rather than a redeploy.
--   * An email comparison in the frontend is worthless (anyone can edit the
--     bundle) and an email comparison in the backend is only as good as the
--     one code path that remembers to do it.
--
-- REFERENCES auth.users so an owner row cannot outlive the account, and so a
-- typo'd id is rejected at write time instead of silently granting nobody.
CREATE TABLE IF NOT EXISTS app_owners (
    user_id     uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    granted_at  timestamptz NOT NULL DEFAULT now(),
    -- Who granted it. NULL for the first owner, who by definition was granted
    -- by an operator running SQL rather than by another owner.
    granted_by  uuid REFERENCES auth.users(id) ON DELETE SET NULL,
    note        text
);

COMMENT ON TABLE app_owners IS
    'Accounts allowed to change global application configuration.';

ALTER TABLE app_owners ENABLE ROW LEVEL SECURITY;

-- A signed-in user may read ONLY their own row. That is enough for the
-- interface to decide whether to render the owner section, and it does not let
-- one user enumerate who the owners are.
--
-- There is deliberately NO insert/update/delete policy. With RLS enabled and
-- no write policy, the table is append-only from outside: ownership can only
-- be granted through the SQL editor, by someone who already has database
-- access. That is the correct bar for the privilege it confers.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'app_owners' AND policyname = 'app_owners_read_own'
    ) THEN
        CREATE POLICY app_owners_read_own ON app_owners
            FOR SELECT USING (user_id = auth.uid());
    END IF;
END $$;


-- ------------------------------------------------------------
-- 2. system_settings: global configuration
-- ------------------------------------------------------------
-- Key/value rather than one column per setting. There is exactly one setting
-- today (`active_ai_provider`) and a column would be tidier for that one case,
-- but every further setting would then be a migration plus a deploy. A keyed
-- table makes the next one an INSERT.
--
-- Values are `text`, not `jsonb`: every setting so far is a short scalar, and
-- jsonb would mean every reader has to unwrap a JSON string to get a word.
CREATE TABLE IF NOT EXISTS system_settings (
    key         text PRIMARY KEY,
    value       text NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

COMMENT ON TABLE system_settings IS
    'Global application configuration. Readable by any signed-in user, '
    'writable only by an account listed in app_owners.';
COMMENT ON COLUMN system_settings.value IS
    'NEVER an API key or any other secret. Secrets live in the server '
    'environment. This table is readable by every signed-in user.';

ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    -- Any signed-in user may READ. The active provider is not a secret - it is
    -- shown on every analysis result - and the analysis path needs it on every
    -- request, made with that user's own token.
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'system_settings' AND policyname = 'system_settings_read'
    ) THEN
        CREATE POLICY system_settings_read ON system_settings
            FOR SELECT USING (auth.uid() IS NOT NULL);
    END IF;

    -- Only an owner may WRITE. Split into INSERT and UPDATE rather than FOR
    -- ALL so that neither DELETE nor a surprise TRUNCATE-by-policy is ever
    -- permitted: a missing settings row and a wrong one fail differently, and
    -- only one of them is recoverable by the interface.
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'system_settings' AND policyname = 'system_settings_owner_insert'
    ) THEN
        CREATE POLICY system_settings_owner_insert ON system_settings
            FOR INSERT WITH CHECK (
                EXISTS (SELECT 1 FROM app_owners o WHERE o.user_id = auth.uid())
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'system_settings' AND policyname = 'system_settings_owner_update'
    ) THEN
        CREATE POLICY system_settings_owner_update ON system_settings
            FOR UPDATE USING (
                EXISTS (SELECT 1 FROM app_owners o WHERE o.user_id = auth.uid())
            )
            WITH CHECK (
                EXISTS (SELECT 1 FROM app_owners o WHERE o.user_id = auth.uid())
            );
    END IF;
END $$;

-- Only two provider values are legal. The CHECK is on the DATA rather than in
-- the application, so a hand-edited row cannot put the analysis path into a
-- state it has no code path for. It is written as a general constraint keyed
-- on `key` so other settings are unaffected.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'system_settings_known_values'
    ) THEN
        ALTER TABLE system_settings ADD CONSTRAINT system_settings_known_values
            CHECK (
                key <> 'active_ai_provider'
                OR value IN ('anthropic', 'groq')
            );
    END IF;
END $$;

-- The starting value. ON CONFLICT DO NOTHING so re-running never overwrites an
-- owner's actual choice with the default.
INSERT INTO system_settings (key, value)
VALUES ('active_ai_provider', 'anthropic')
ON CONFLICT (key) DO NOTHING;

CREATE INDEX IF NOT EXISTS system_settings_updated_at_idx
    ON system_settings (updated_at DESC);


-- ------------------------------------------------------------
-- 3. analyses: record WHICH model actually produced the result
-- ------------------------------------------------------------
-- `analyses.model_used` already existed and is kept unchanged. These add the
-- facts it cannot express on its own: which vendor, whether the primary
-- provider failed, and how long it took.
--
-- This is what makes a later Claude-versus-Groq comparison possible from
-- stored data rather than from memory.
--
-- ALL NULLABLE, ALL WITHOUT BACKFILL. An analysis produced before this
-- migration genuinely has no recorded provider, and writing one in would be
-- inventing provenance for a result nobody observed. NULL reads as "not
-- recorded", which is true.
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS model_provider     text;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS fallback_used      boolean;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS fallback_provider  text;
ALTER TABLE analyses ADD COLUMN IF NOT EXISTS processing_time_ms integer;

COMMENT ON COLUMN analyses.model_provider IS
    'Vendor that ACTUALLY produced this analysis (anthropic | groq | gemini '
    'for historical rows). If the primary failed over, this is the fallback. '
    'NULL means the analysis predates this column.';
COMMENT ON COLUMN analyses.fallback_used IS
    'True when the primary provider failed and the other one produced the '
    'result. NULL means not recorded.';
COMMENT ON COLUMN analyses.processing_time_ms IS
    'Wall-clock milliseconds for the analysis. Real measurement only.';

-- Supports the evaluation query "group results by provider".
CREATE INDEX IF NOT EXISTS analyses_model_provider_idx
    ON analyses (model_provider);


-- ------------------------------------------------------------
-- 4. GRANTING THE FIRST OWNER  (manual, on purpose)
-- ------------------------------------------------------------
-- This migration deliberately grants ownership to NOBODY. There is no way for
-- a migration to know which account should hold it, and guessing - "the first
-- user to register", say - would hand global configuration to whoever signed
-- up first.
--
-- After creating your account and signing in once, find your id in
-- Supabase Dashboard -> Authentication -> Users, then run:
--
--     INSERT INTO app_owners (user_id, note)
--     VALUES ('YOUR-USER-ID', 'project owner')
--     ON CONFLICT (user_id) DO NOTHING;
--
-- Alternatively, set the OWNER_EMAIL environment variable on the server. The
-- backend treats a verified token whose email matches it as an owner, which
-- avoids this manual step. That comparison is made server-side against the
-- email on a token Supabase has already verified - never against a value the
-- browser supplied.


-- ------------------------------------------------------------
-- 5. Verification
-- ------------------------------------------------------------
-- (a) The two new tables exist. Expect 2 rows.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('app_owners', 'system_settings')
ORDER BY table_name;

-- (b) The starting configuration. Expect one row: active_ai_provider = anthropic
--     (or whatever an owner has since chosen).
SELECT key, value, updated_at FROM system_settings ORDER BY key;

-- (c) The new analysis columns. Expect 4 rows.
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'analyses'
  AND column_name IN
      ('model_provider', 'fallback_used', 'fallback_provider', 'processing_time_ms')
ORDER BY column_name;

-- (d) Legacy data untouched. Expect papers = 2, analyses = 2,
--     literature_reviews = 1, and every one of them still unowned.
SELECT
    (SELECT count(*) FROM papers)                                   AS papers,
    (SELECT count(*) FROM analyses)                                 AS analyses,
    (SELECT count(*) FROM literature_reviews)                       AS reviews,
    (SELECT count(*) FROM analyses WHERE model_provider IS NULL)    AS analyses_without_provider,
    (SELECT count(*) FROM papers WHERE user_id IS NULL)             AS papers_still_unowned;

-- (e) Who owns the application. Expect 0 rows until section 4 is done.
SELECT user_id, granted_at, note FROM app_owners ORDER BY granted_at;
