-- Add the categorical primary_theme cause signal to policy decisions.
-- The policy_analysis pipeline now extracts a controlled-vocabulary primary_theme
-- (18-label COFOG theme list, see llm.gemini.policy_themes) for each decision.
-- Persisted here so trending-causes can be rebuilt from bronze.bronze_policy_decisions
-- (parallel to the legacy bronze_decisions_from_ai.primary_theme signal).
--
-- Idempotent: re-applied on every persist call via persist_policy_analysis_bronze.
-- Nullable on purpose — older cached analyses / in-flight runs may not carry a theme.
--
-- Apply: psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
--   -f packages/hosting/scripts/neon/migrations/106_policy_decisions_primary_theme.sql

BEGIN;

ALTER TABLE bronze.bronze_policy_decisions
    ADD COLUMN IF NOT EXISTS primary_theme TEXT;

COMMENT ON COLUMN bronze.bronze_policy_decisions.primary_theme IS
    'Controlled-vocabulary civic decision theme (18-label COFOG list, see '
    'llm.gemini.policy_themes.PRIMARY_THEMES). Nullable. Cause signal for '
    'trending-causes rebuild.';

COMMIT;
