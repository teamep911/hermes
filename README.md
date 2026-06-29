# Hermes — OEM Oracle monitoring on Nous Hermes Agent

This repo is **not** a custom agent. It is the deployment kit that turns
[Nous Research **Hermes Agent**](https://github.com/NousResearch/hermes-agent)
into an Oracle/OEM incident-RCA assistant: OEM pushes an alert → Hermes runs the
right Oracle skill with its built-in memory and your own model endpoint → the
result is delivered to a Google Chat space.

Webhook ingestion (with HMAC), skills, persistent memory and model routing are
**native Hermes features**; we supply the Oracle-specific pieces. Google Chat is
delivered via the space **incoming webhook** (one-way, no GCP project) using the
`notify-google-chat` skill — the native Chat plugin needs Pub/Sub+GCP, which this
deployment avoids.

```
OEM / DB host (Oracle · Linux)             Hermes Agent gateway (Linux VPS, systemd)
┌──────────────────────────────┐          ┌─────────────────────────────────────────────┐
│ threshold / lock alert        │          │ webhook adapter  /webhooks/oem-alert (HMAC)   │
│ awr_export.sh · check_session │  POST    │   ▼                                           │
│ redact.py  (mask IP/host/...) │ ───────► │ skill: alert-triage | oracle-rca | awr-summary│
│ alert_push.sh → curl          │ (masked) │   ▼  (your own model endpoint)                │
└──────────────────────────────┘          │ Hermes memory: past incidents / similar errors│
                                           │   ▼                                           │
                                           │ notify-google-chat skill → incoming webhook ──┼──► Google Chat space
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
| `skills/oracle/notify-google-chat/` | Deliver the RCA to Google Chat via incoming webhook (`scripts/gchat_send.sh`) |
| `deploy/webhook-route.yaml` | `oem-alert` webhook route to MERGE into config.yaml |
| `deploy/hermes.env.example` | Secrets template (`~/.hermes/.env`) |
| `deploy/hermes-gateway.service` | systemd unit for the headless gateway |

## Security model

- **Masking happens on the OEM/DB host** (`redact.py`), *before* the payload ever
  leaves. The agent and the LLM only see opaque placeholders (`<IP_1>`, `<HOST_2>`).
- **Your own model endpoint.** Hermes is already configured with
  `model.provider: custom` pointing at an internal OpenAI-compatible endpoint —
  the (already-masked) data never goes to a public provider. This deployment does
  **not** change that.
- **Inbound HMAC.** The OEM payload is signed (`X-Webhook-Signature` = hex
  HMAC-SHA256) with a shared `WEBHOOK_SECRET`; Hermes rejects unsigned requests.
  (openssl↔python interop verified.)
- Secrets live only in `~/.hermes/.env`; this repo ships placeholders.

## Deploy (gateway host)

Verified against Hermes Agent **v0.17.0**.

```bash
# 1. Install the Oracle skills (category "oracle"):
mkdir -p ~/.hermes/skills/oracle
cp -r skills/oracle/* ~/.hermes/skills/oracle/
hermes skills list | grep oracle        # -> alert-triage / awr-summary / oracle-rca, enabled

# 2. MERGE the webhook route into your existing config (do NOT overwrite it —
#    your model/memory settings must stay). See deploy/webhook-route.yaml.
$EDITOR ~/.hermes/config.yaml           # paste the platforms.webhook block

# 3. Create a Google Chat incoming webhook in the target space
#    (Apps & integrations -> Webhooks -> Add). Copy its URL.

# 4. Add secrets:
cat deploy/hermes.env.example >> ~/.hermes/.env && chmod 600 ~/.hermes/.env
# fill in WEBHOOK_SECRET and GOOGLE_CHAT_WEBHOOK_URL (the model endpoint is already set)

# 5. Run headless:
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
