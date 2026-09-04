-- ============================================================
-- ResearchForge, Migration 006: AI provider availability
-- ============================================================
-- Builds on 004, which created system_settings and app_owners. Run it first.
--
-- WHAT THIS ADDS
-- --------------
-- One setting: which providers the owner permits at all.
--
--     enabled_ai_providers = 'anthropic,groq'   both usable (the default)
--                          | 'anthropic'        Groq switched off
--                          | 'groq'             Claude switched off
--
-- A provider that is switched off is never called - not as primary, and not
-- as a fallback. `active_ai_provider` continues to say WHICH of the enabled
-- providers leads; this says which are permitted at all. The two together are
-- the whole configuration.
--
-- WHY ONE ROW RATHER THAN groq_enabled + anthropic_enabled
-- --------------------------------------------------------
-- Two boolean rows can both be false. That state has no correct behaviour -
-- every analysis would fail - and preventing it across two rows needs a
-- trigger, or application code that remembers to check.
--
-- A single value holding the SET makes the bad state unrepresentable: the
-- CHECK below simply does not include an empty option. The database refuses
-- it, so no code path can produce it, including a hand-edited row in the
-- dashboard. The invariant lives with the data instead of with whoever
-- remembers to enforce it.
--
-- The value is kept alphabetically sorted so 'anthropic,groq' is the only
-- spelling of "both" and comparisons stay simple.
--
-- ⚠️  TARGET: the ResearchForge Supabase project ONLY. NEVER RPOMS.
--
-- SAFETY: ADDITIVE ONLY. It inserts one row and adds one CHECK constraint
--   scoped to the new key. No DROP, no TRUNCATE, no DELETE, no ALTER of an
--   existing column, and no change to any existing row - `active_ai_provider`
--   and every app_owners entry are untouched. RLS is not modified: the
--   policies from 004 already restrict writes to owners, and this new key is
--   covered by them automatically because it lives in the same table.
--   Re-running is safe.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> New query -> paste -> Run
-- ============================================================


-- ------------------------------------------------------------
-- 1. The permitted values
-- ------------------------------------------------------------
-- Three sets, and deliberately no empty one. "Both providers off" is not a
-- configuration the application can be left in, so it is not a value the
-- column can hold.
--
-- A SEPARATE constraint from 004's `system_settings_known_values`, not a
-- replacement: rewriting that one would mean dropping it, and this migration
-- drops nothing. Postgres ANDs the two together, so each key is governed by
-- its own rule and neither can weaken the other.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'system_settings_enabled_providers'
    ) THEN
        ALTER TABLE system_settings ADD CONSTRAINT system_settings_enabled_providers
            CHECK (
                key <> 'enabled_ai_providers'
                OR value IN ('anthropic', 'groq', 'anthropic,groq')
            );
    END IF;
END $$;


-- ------------------------------------------------------------
-- 2. The starting value: everything on
-- ------------------------------------------------------------
-- Both enabled, which is exactly how the application behaves today - so
-- running this migration changes no behaviour until the owner chooses to
-- switch something off.
--
-- ON CONFLICT DO NOTHING so re-running never overwrites a real choice.
INSERT INTO system_settings (key, value)
VALUES ('enabled_ai_providers', 'anthropic,groq')
ON CONFLICT (key) DO NOTHING;

COMMENT ON CONSTRAINT system_settings_enabled_providers ON system_settings IS
    'Provider availability is a non-empty set. "Both off" is unrepresentable '
    'by design - every analysis would fail and there is no correct behaviour.';


-- ------------------------------------------------------------
-- 3. Verification
-- ------------------------------------------------------------
-- (a) Both settings present, and the pre-existing one UNCHANGED. Expect
--     active_ai_provider at whatever the owner had chosen, and
--     enabled_ai_providers = 'anthropic,groq'.
SELECT key, value, updated_at FROM system_settings ORDER BY key;

-- (b) Both CHECK constraints exist side by side. Expect two rows:
--     system_settings_known_values (from 004) and
--     system_settings_enabled_providers (this migration).
SELECT conname FROM pg_constraint
WHERE conrelid = 'system_settings'::regclass AND contype = 'c'
ORDER BY conname;

-- (c) RLS unchanged - still owner-only for writes. Expect the three policies
--     from 004: system_settings_read, _owner_insert, _owner_update.
SELECT policyname, cmd FROM pg_policies
WHERE schemaname = 'public' AND tablename = 'system_settings'
ORDER BY policyname;

-- (d) Nothing else moved. Expect papers 4, analyses 4, reviews 1, and the
--     owner and cache rows exactly as they were.
SELECT
    (SELECT count(*) FROM papers)             AS papers,
    (SELECT count(*) FROM analyses)           AS analyses,
    (SELECT count(*) FROM literature_reviews) AS reviews,
    (SELECT count(*) FROM analysis_cache)     AS cache_entries,
    (SELECT count(*) FROM app_owners)         AS owners;

-- (e) OPTIONAL sanity check that the constraint really refuses an empty set.
--     Uncomment to run; it is EXPECTED TO FAIL with a check violation, and
--     it changes nothing when it does.
--
-- UPDATE system_settings SET value = '' WHERE key = 'enabled_ai_providers';
