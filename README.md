# Hermes — OEM Oracle monitoring on Nous Hermes Agent

This repo is **not** a custom agent. It is the deployment kit that turns
[Nous Research **Hermes Agent**](https://github.com/NousResearch/hermes-agent)
into an Oracle/OEM incident-RCA assistant: OEM pushes an alert → Hermes runs the
right Oracle skill with its built-in memory and your Claude model → the result
lands in a Google Chat space.

Webhook ingestion (with HMAC), skills, persistent memory, multi-model routing and
Google Chat are **native Hermes features** — we only supply the Oracle-specific
pieces.

```
OEM / DB host (Oracle · Linux)             Hermes Agent gateway (Linux VPS, systemd)
┌──────────────────────────────┐          ┌─────────────────────────────────────────────┐
│ threshold / lock alert        │          │ webhook adapter  /webhooks/oem-alert (HMAC)   │
│ awr_export.sh · check_session │  POST    │   ▼                                           │
│ redact.py  (mask IP/host/...) │ ───────► │ skill: alert-triage | oracle-rca | awr-summary│
│ alert_push.sh → curl          │ (masked) │   ▼  (your Anthropic/Claude key)              │
└──────────────────────────────┘          │ Hermes memory: past incidents / similar errors│
                                           │   ▼                                           │
                                           │ Google Chat (Pub/Sub + Chat REST, 2-way)      │
                                           └─────────────────────────────────────────────┘
```

## What this repo provides

| Path | Role |
|------|------|
| `scripts/awr_export.sh` | Generate a trimmed text AWR report (OEM host) |
| `scripts/check_session.sh` | Dump blocking/locking sessions (OEM host) |
| `scripts/redact.py` | **Mask IP/host/domain/secrets on the DB host** (stdlib only) |
| `scripts/alert_push.sh` | Redact → build payload → HMAC-sign → POST to Hermes |
| `skills/oracle/alert-triage/` | Generic OEM alert triage skill |
| `skills/oracle/oracle-rca/` | Lock / blocking-session RCA skill |
| `skills/oracle/awr-summary/` | AWR performance summary skill |
| `deploy/config.yaml` | Hermes config: Claude model + `oem-alert` webhook route |
| `deploy/hermes.env.example` | Secrets template (`~/.hermes/.env`) |
| `deploy/hermes-gateway.service` | systemd unit for the headless gateway |

## Security model

- **Masking happens on the OEM/DB host** (`redact.py`), *before* the payload ever
  leaves. The agent and the LLM only see opaque placeholders (`<IP_1>`, `<HOST_2>`).
- **Your own Claude key.** `deploy/config.yaml` sets `model.provider: anthropic`
  with `ANTHROPIC_API_KEY` from `~/.hermes/.env` — billed pay-per-token on your
  org, not routed through Nous Portal.
- **Inbound HMAC.** The OEM payload is signed (`X-Webhook-Signature`) with a shared
  `WEBHOOK_SECRET`; Hermes rejects unsigned requests.
- Secrets live only in `~/.hermes/.env`; this repo ships placeholders.

## Deploy (gateway host)

```bash
# 1. Install Hermes Agent (see its docs / releases), then:
mkdir -p ~/.hermes/skills/oracle
cp -r skills/oracle/* ~/.hermes/skills/oracle/
cp deploy/config.yaml ~/.hermes/config.yaml
cp deploy/hermes.env.example ~/.hermes/.env && chmod 600 ~/.hermes/.env
# fill in ANTHROPIC_API_KEY, WEBHOOK_SECRET, GOOGLE_CHAT_* in ~/.hermes/.env

# 2. Provision Google Chat (service account + Pub/Sub subscription):
hermes gateway setup

# 3. Run headless:
sudo cp deploy/hermes-gateway.service /etc/systemd/system/
sudo systemctl enable --now hermes-gateway
```

## OEM host

```bash
# Copy scripts/ to the DB host. The OEM notification method runs:
HERMES_URL=http://<hermes-host>:8644/webhooks/oem-alert \
WEBHOOK_SECRET=<same-as-config> \
ALERT_TYPE=lock TARGET_NAME=<db> SEVERITY=critical MESSAGE="ORA-00060 ..." \
  ./scripts/alert_push.sh
```

## Tests

```bash
python3 -m pytest tests/ -q     # masking: no-leak + stable placeholders
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design and the open
items still to confirm against the installed Hermes version.
