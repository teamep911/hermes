# Central VM — as built

This host is the **VM trung tâm** of Architecture Option 2
([docs/architecture_option2.md](../docs/architecture_option2.md)). Native
installs, one OS user per service, systemd — no Docker.

## Services (all running)

| Service | systemd unit | User | Bind | Role |
|---------|--------------|------|------|------|
| PostgreSQL 17 | `postgresql-17` | postgres | 127.0.0.1:5432 | `dds` + `meta` DBs |
| InfluxDB 2 | `influxdb` | influxdb | :8086 | metrics store (`central`/`metrics`, 30d) |
| Loki | `loki` | loki | :3100 | log store |
| MCP server | `mcp_svc` | mcp_svc | 127.0.0.1:9000 | read-only DDS/META tools for Hermes |
| Normalizer | `normalize.timer`→`.service` | dds_db | — | InfluxDB → `dds.metric_rollup`, every 60s |
| Hermes gateway | `--user hermes-gateway` | root* | :8644 | webhook (Luồng A) + MCP client + Google Chat |

\* Hermes still runs as root; migrate to `hermes_svc` (user exists) — see below.

## Two flows converge at Hermes

- **Luồng A (event):** OEM → `:8644/webhooks/oem-alert` (HMAC) → agent → Google
  Chat. No MCP. (Verified.)
- **Luồng B (polling):** DB-host Telegraf → InfluxDB → normalizer → `dds` →
  **MCP** (`mcp_servers.dds` in Hermes) → agent tools `recent_metrics`,
  `recent_events`, `list_instances`, `incident_history`. (MCP tools registered
  & verified; live metrics arrive once DB-host Telegraf is deployed.)

## Install order (reproduce)

1. `users/create-service-users.sh`
2. PostgreSQL 17 (PGDG repo) → `postgres/schema_dds.sql`, `schema_meta.sql`;
   roles `dds_db` (owner) + `mcp_ro` (SELECT-only).
3. InfluxDB 2 → `influx setup` org `central` / bucket `metrics`; write token
   (Telegraf) + read token (normalizer).
4. Loki → `loki/loki-config.yaml` + `loki/loki.service`.
5. MCP → venv (`mcp-server/requirements.txt`) + `server.py` + `mcp_svc.service`;
   add `mcp_servers.dds` to `~/.hermes/config.yaml`.
6. Normalizer → venv + `normalize.py` + `normalize.{service,timer}`.
7. Hermes → keep `hermes/` (webhook route, gchat_webhook plugin, skills).

## Secrets (NOT in repo)

- `/opt/mcp/db.env` — mcp_ro creds (SELECT-only) — owner mcp_svc, 0600
- `/opt/dds/db.env` — dds_db creds + InfluxDB read token — owner dds_db, 0600
- `/root/.influx_central.env` — Influx admin + Telegraf write token
- `~/.hermes/.env`, `~/.hermes/config.yaml` — Hermes model/webhook/Google Chat

## Deferred / off-host

- **n8n** — runs off-host; `n8n/` is scaffold only (Hermes calls it by URL).
- **Splunk** — separate audit VM, a later phase (not wired yet).

## Recommended hardening follow-up

Migrate Hermes from root → `hermes_svc` (the gateway's security audit flags
root). Reinstall the user gateway under `hermes_svc` and move `~/.hermes`.
