# Hermes fleet monitoring — Architecture Option 2 (Telegraf + MCP + Hermes)

On-prem monitoring + AI-RCA for a fleet of 30-100 DB instances (Oracle,
Postgres, MySQL, MongoDB, SQL Server). Design:
[docs/architecture_option2.md](docs/architecture_option2.md).

Two flows converge at **Nous Hermes Agent**, which analyses with your own model
and delivers to Google Chat:

- **Luồng A (event):** OEM Metric Alert → `alert_push.sh` → Hermes webhook → RCA.
- **Luồng B (polling):** DB-host Telegraf → InfluxDB/Loki → normalizer → DDS/META
  → MCP server → Hermes tools.

## Repo layout (by host role)

| Path | Host | Contents |
|------|------|----------|
| [central-vm/](central-vm/) | VM trung tâm (this machine) | Postgres (DDS+META), InfluxDB, Loki, MCP server, normalizer, Hermes, per-service users. **As-built: [central-vm/README.md](central-vm/README.md)** |
| [oem-host/](oem-host/) | OEM host | `alert_push.sh` + collectors + `redact.py` (mask before send) + preflight |
| [db-hosts/](db-hosts/) | 30-100 DB hosts | Ansible playbook + Telegraf config + `oracle_metrics.sh` |
| [docs/](docs/) | — | `architecture_option2.md` (design), `ARCHITECTURE.md` (Luồng A / Hermes detail), `OEM_SETUP.md` |

## Status

- **Central VM: installed & running** — Postgres 17 (`dds`+`meta`), InfluxDB 2,
  Loki, MCP server (4 read-only tools, registered in Hermes), normalizer timer,
  Hermes gateway (webhook + Google Chat). See central-vm/README.md.
- **OEM host:** scripts ready ([docs/OEM_SETUP.md](docs/OEM_SETUP.md)); wire on the OEM machine.
- **DB hosts:** Ansible scaffold ready; run at scale when hosts are available.
- **n8n:** off-host (scaffold only). **Splunk:** separate audit VM, later phase.

## Principles

- **No Docker** — native installs, one OS user per service, systemd isolation.
- **Masking on the source** — `redact.py` scrubs IP/host/domain/secrets on the
  DB/OEM host before anything leaves.
- **MCP is read-only** — the server connects as a SELECT-only Postgres role.
- Secrets live under `/opt/*/db.env` and `~/.hermes/` — never in the repo.
