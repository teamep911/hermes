# Architecture

## Topology

A single Linux VPS runs the `hermes-gateway` systemd service (FastAPI +
uvicorn). The OEM/DB host only runs shell collectors that POST to it.

```
OEM/DB host  ──HTTPS POST (HMAC)──►  Hermes VPS  ──HTTPS──►  Google Chat space
                                         │
                                         └── LLM providers (Claude/Gemini/OpenRouter)
                                         └── PostgreSQL + pgvector (local)
```

## Request lifecycle (`hermes/pipeline.py`)

1. **Receive** — `POST /webhook/oem`, body verified with HMAC-SHA256
   (`X-Hermes-Signature`, shared `AGENT_WEBHOOK_SECRET`).
2. **Severity gate** — drop alerts below `LLM_MIN_SEVERITY` (no LLM cost).
3. **Dedup gate** — drop signatures seen within `DEDUP_WINDOW_SECONDS`.
4. **Redact** — `security/redactor.py` masks IPs, hostnames, domains, emails,
   connect strings and secrets into stable placeholders (`<IP_1>`, `<HOST_2>`…).
   This is the only form that ever leaves the process or hits the DB.
5. **Recall** — embed the redacted text, cosine-search `incident_embedding`
   (pgvector) for the top-K similar past incidents above `MEMORY_MIN_SCORE`.
6. **Skill** — `select_skill()` routes by alert type:
   - `lock` / `block` / `session` → `rca_oracle`
   - CPU/IO/memory threshold or AWR present → `awr_summary`
   - otherwise → `analyze_alert`
   The skill makes **one** structured LLM call (JSON contract) via the router.
7. **Persist** — store the incident + embedding (redacted) for future recall.
8. **Deliver** — format a Cards v2 message and POST to the Google Chat webhook.

## LLM routing (`hermes/llm/router.py`)

`LLM_PRIMARY` then `LLM_FALLBACKS` in order. A provider is skipped if its API
key is absent and retried on the next provider on `LLMError` (timeout, auth,
rate-limit, malformed response). Default chain: `claude → gemini → openrouter`.

## Memory (`hermes/memory/`)

- Embeddings: `voyage` or `gemini`, with an offline deterministic `hash`
  fallback so the recall path works without any embedding key.
- `incident` holds redacted summary/root-cause + full `rca_json`.
- `incident_embedding` holds the `vector(EMBEDDING_DIM)` with an ivfflat cosine
  index. Keep `EMBEDDING_DIM` in `.env.runtime` in sync with the schema.

## Security model

- **Inbound trust:** HMAC-SHA256 over the raw body; constant-time compare.
- **Outbound data minimisation:** redaction before LLM calls and before storage.
- **Secrets:** only in `.env.runtime` (chmod 600, git-ignored). The repo carries
  placeholders only.
- **systemd hardening:** `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`,
  `ProtectHome`.

## What changed from the legacy `agent_gcp`

| Legacy | Hermes |
|--------|--------|
| RCA = static rule template | RCA = LLM skill + recalled memory |
| Separate agent + GCP gateway hosts (2 HMAC hops) | Single VPS, Chat as in-process toolset |
| Incident table only | pgvector similar-error recall |
| No LLM | Multi-provider router with fallback |
| Raw OS-command alert | Enriched payload (AWR + session dump) |
