-- DDS DB — Diagnostic Data Store: normalized facts the MCP server exposes to
-- Hermes. Filled by the normalization job (from InfluxDB/Loki) and the webhook
-- flow (OEM events). Owned by dds_db; MCP role has SELECT only.
--   psql -U dds_db -d dds -f schema_dds.sql

-- Rolled-up metrics (normalized from InfluxDB by the cron job).
CREATE TABLE IF NOT EXISTS metric_rollup (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance     TEXT NOT NULL,                -- db_instance.name
    metric       TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end   TIMESTAMPTZ NOT NULL,
    avg_val      DOUBLE PRECISION,
    max_val      DOUBLE PRECISION,
    min_val      DOUBLE PRECISION,
    last_val     DOUBLE PRECISION,
    UNIQUE (instance, metric, window_start)
);
CREATE INDEX IF NOT EXISTS idx_rollup_instance_metric ON metric_rollup (instance, metric, window_start DESC);

-- Normalized events: OEM alerts (webhook flow) + notable log lines (Loki).
CREATE TABLE IF NOT EXISTS db_event (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance     TEXT NOT NULL,
    event_type   TEXT NOT NULL,                -- threshold|lock|block|session|log
    severity     TEXT NOT NULL DEFAULT 'warning',
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source       TEXT NOT NULL DEFAULT 'oem',  -- oem|loki|telegraf
    signature    TEXT,                         -- for dedup / similar-error lookup
    detail       JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_event_instance_time ON db_event (instance, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_event_signature ON db_event (signature);

-- RCA results written back by Hermes (optional; for similar-incident recall).
CREATE TABLE IF NOT EXISTS incident (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instance     TEXT NOT NULL,
    signature    TEXT,
    summary      TEXT,
    root_cause   TEXT,
    rca_json     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_incident_instance_time ON incident (instance, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_signature ON incident (signature);
