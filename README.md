# Hermes Agent

LLM-assisted RCA gateway for Oracle / OEM alerts.

```
OEM host (Oracle · Linux)                Hermes Agent host (Linux VPS · hermes-gateway systemd)
┌─────────────────────────┐              ┌────────────────────────────────────────────────────┐
│ threshold / lock alert  │   HTTP POST  │ Webhook receiver  (HMAC-SHA256)                      │
│ awr_export.sh           │  ─────────►  │   ▼                                                  │
│ check_session.sh        │   (1 payload)│ Redactor  → mask IP / host / domain / secrets        │
│ alert_push.sh → curl    │              │   ▼                                                  │
└─────────────────────────┘              │ Memory (pgvector): incident history · similar errors │
                                         │   ▼                                                  │
                                         │ Skills: analyze_alert · rca_oracle · awr_summary     │
                                         │   ▼                                                  │
                                         │ LLM analysis: Claude → Gemini → OpenRouter (fallback)│
                                         │   ▼                                                  │
                                         │ Response formatter (markdown / Cards v2)             │
                                         │   ▼                                                  │
                                         │ Google Chat toolset ─────────────► Google Chat space │
                                         └────────────────────────────────────────────────────┘
```

## Why this design

- **Single VPS topology.** Webhook + analysis + Google Chat delivery run in one
  `hermes-gateway` process — one fewer HMAC hop than the old split agent/gateway.
- **LLM RCA, not static templates.** Each alert is analysed by a skill backed by
  a real LLM with recalled context, instead of a fixed rule template.
- **Security first.** Oracle context (AWR, sessions, messages) is **redacted**
  (IPs, hostnames, domains, secrets → opaque placeholders) *before* any byte
  leaves for an external provider. Only redacted text is stored in the DB.
- **Prompt-chain, not an agent loop.** OEM ships a full payload; the skill makes a
  single structured LLM call. Simple, cheap, predictable.

## Components

| Path | Role |
|------|------|
| `hermes/main.py` | FastAPI app: `/webhook/oem`, `/health`, `/google-chat/command` |
| `hermes/security/` | HMAC auth + redactor (masking) |
| `hermes/llm/` | Provider router: Claude (default) → Gemini → OpenRouter |
| `hermes/skills/` | `analyze_alert`, `rca_oracle`, `awr_summary` |
| `hermes/memory/` | pgvector recall + persist, embeddings |
| `hermes/pipeline.py` | Orchestrates redact → recall → skill → persist → deliver |
| `hermes/formatter.py` | RcaResult → markdown / Google Chat Cards v2 |
| `hermes/chat/` | Google Chat outbound toolset |
| `scripts/` | OEM-side collectors: `awr_export.sh`, `check_session.sh`, `alert_push.sh` |
| `infra/sql/schema.sql` | PostgreSQL + pgvector schema |
| `infra/systemd/` | `hermes-gateway.service` |

## Setup

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env.runtime && chmod 600 .env.runtime   # fill in secrets

createdb hermes
psql hermes -f infra/sql/schema.sql

uvicorn hermes.main:app --host 0.0.0.0 --port 2020
```

Set at minimum: `AGENT_WEBHOOK_SECRET`, `PG_DSN`, one LLM API key
(`ANTHROPIC_API_KEY`), and `GOOGLE_CHAT_WEBHOOK_URL`.

## Configuration

All hostnames, IPs, domains and secrets come from `.env.runtime` (git-ignored).
The repository ships only `.env.example` with placeholders. See it for the full
list. Cost controls: `LLM_MIN_SEVERITY` (severity gate) and `DEDUP_WINDOW_SECONDS`
(skip repeated signatures).

## Tests

```bash
pytest -q
```

`tests/test_redactor.py` includes a no-leak assertion that fails if any IP /
host / domain survives redaction.
