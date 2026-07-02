-- META DB — inventory / metadata about the monitored fleet.
-- Owned by dds_db; MCP role has SELECT only.
--   psql -U dds_db -d meta -f schema_meta.sql

CREATE TABLE IF NOT EXISTS db_instance (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,          -- logical name, e.g. ORCLPROD
    db_type     TEXT NOT NULL,                 -- oracle|postgres|mysql|mongodb|sqlserver
    host        TEXT,                          -- redacted/placeholder in shared contexts
    port        INT,
    environment TEXT DEFAULT 'prod',           -- prod|uat|dev
    owner_team  TEXT,
    tags        JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS metric_catalog (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    db_type     TEXT NOT NULL,
    metric      TEXT NOT NULL,                 -- e.g. cpu_util, active_sessions, blocking_count
    unit        TEXT,
    description TEXT,
    UNIQUE (db_type, metric)
);

CREATE INDEX IF NOT EXISTS idx_db_instance_type ON db_instance (db_type);
