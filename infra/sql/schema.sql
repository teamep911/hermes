-- Hermes Agent — database schema (PostgreSQL + pgvector)
-- Run once against the database referenced by PG_DSN.
--   createdb hermes && psql hermes -f infra/sql/schema.sql
-- NOTE: only redacted text is ever stored here.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS incident (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signature    TEXT        NOT NULL,
    alert_type   TEXT        NOT NULL,
    target_name  TEXT,
    severity     TEXT        NOT NULL DEFAULT 'warning',
    summary      TEXT,
    root_cause   TEXT,
    rca_json     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_incident_signature ON incident (signature);
CREATE INDEX IF NOT EXISTS idx_incident_created_at ON incident (created_at DESC);

-- Embedding dimension must match EMBEDDING_DIM in .env.runtime (default 1024).
CREATE TABLE IF NOT EXISTS incident_embedding (
    incident_id BIGINT PRIMARY KEY REFERENCES incident(id) ON DELETE CASCADE,
    embedding   vector(1024)
);

-- Approximate nearest-neighbour index for cosine distance recall.
CREATE INDEX IF NOT EXISTS idx_incident_embedding_cos
    ON incident_embedding USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
