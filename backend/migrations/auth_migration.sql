-- ============================================================================
-- AlertIQ auth feature — manual production migration
-- ============================================================================
-- Run this against the production database (Neon) BEFORE deploying the
-- feature/authentication branch.
--
-- Why this file exists: the backend creates *new tables* automatically on
-- startup (SQLModel.metadata.create_all), but it never ALTERs existing
-- tables. The `users` table therefore needs no SQL here — it is created
-- automatically on first startup. The two new columns on existing tables
-- below must be added manually.
--
-- All statements are idempotent (IF NOT EXISTS / WHERE ... IS NULL), so the
-- file is safe to run more than once.
-- ============================================================================

-- 1) Alert assignee — the user (username) an alert is assigned to.
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS assignee VARCHAR;
CREATE INDEX IF NOT EXISTS ix_alerts_assignee ON alerts (assignee);

-- 2) Per-source webhook secret — required for /ingest authentication.
ALTER TABLE sources ADD COLUMN IF NOT EXISTS webhook_secret VARCHAR;

-- Backfill a random secret for every existing source. Ingest requests for a
-- source with a NULL secret are rejected (401), so existing sources would
-- stop ingesting until they have one.
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_bytes
UPDATE sources
SET webhook_secret = encode(gen_random_bytes(32), 'hex')
WHERE webhook_secret IS NULL;

-- 3) After running: read the generated secrets and configure each provider
-- (Grafana contact point / Alertmanager webhook_config) to send its secret
-- as the `X-Webhook-Token` HTTP header. The same values are also visible in
-- GET /api/v1/sources/ once logged in.
SELECT id, name, provider_type, webhook_secret FROM sources;

-- ============================================================================
-- Post-deploy (not SQL): create the first admin user by running, from
-- backend/ with DATABASE_URL pointing at production:
--     python -m app.scripts.create_admin <username> <password> [full name]
-- ============================================================================
