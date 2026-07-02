# Architecture — Hermes / Luồng A detail

> This document covers the **Hermes Agent + webhook (Luồng A)** component. The
> overall multi-host design is [architecture_option2.md](architecture_option2.md);
> the central VM as-built is [../central-vm/README.md](../central-vm/README.md).
> Paths moved under `central-vm/hermes/` and `oem-host/scripts/` in the Option 2
> restructure.

## Decision: deploy Nous Hermes Agent, don't rebuild it

The target diagram ("Hermes Agent host" with Skills, Memory, LLM analysis,
Google Chat) maps **1:1 onto native features of Nous Research's
[Hermes Agent](https://github.com/NousResearch/hermes-agent)**. So instead of a
custom service, this repo ships only the Oracle-specific pieces and configures
Hermes to do the rest.

| Diagram box | Native Hermes feature used |
|-------------|----------------------------|
| Webhook receiver | Webhook adapter: HTTP server, HMAC validation, payload→prompt |
| Skills | agentskills.io `SKILL.md` skills in `~/.hermes/skills/` |
| Memory | Agent-curated memory + FTS5 cross-session recall |
| LLM analysis | `model.provider: custom` → your own internal endpoint |
| Google Chat | Space **incoming webhook** via the bundled `gchat_webhook` deliver plugin (no GCP) |
| hermes-gateway (systemd) | `hermes gateway run`, headless |

## Flow

1. **Collect (OEM/DB host).** On alert, `alert_push.sh` runs `check_session.sh`
   (locks) or `awr_export.sh` (perf) to enrich the event.
2. **Redact (OEM/DB host).** `redact.py` masks IPs/hostnames/domains/emails/
   secrets into stable placeholders. **This is the only point masking happens —
   sensitive data never leaves the DB host unmasked.**
3. **Sign + POST.** HMAC-SHA256 over the body, header `X-Webhook-Signature`, to
   `http://<gateway>:8644/webhooks/oem-alert`.
4. **Ingest (Hermes).** The webhook adapter verifies the signature and renders the
   `prompt` template (`deploy/webhook-route.yaml`) from payload fields.
5. **Reason (Hermes).** The route loads the Oracle skills; the agent picks the
   analysis skill by its "When to Use" section and calls your own model endpoint.
   Hermes memory supplies similar past incidents automatically.
6. **Deliver.** The route's `deliver: gchat_webhook` sends the **full** agent
   response to the Google Chat space incoming webhook. This happens at the
   gateway deliver layer — deterministic, independent of whether the agent
   chose to call a tool.

## Skill selection

The route loads three analysis skills; the agent picks one by its "When to Use":
- lock / blocking / session dump → `oracle-rca`
- CPU/IO/memory threshold with AWR → `awr-summary`
- everything else → `alert-triage`

(On a local model that doesn't tool-call, the webhook auto-invokes the first
skill's context; the agent still produces a full RCA. Delivery is handled by the
plugin, not a skill.)

## Google Chat delivery: incoming webhook via a platform plugin (no GCP)

The user has Google Workspace but no GCP project. Hermes' native `google_chat`
plugin needs a GCP project + service account + Cloud Pub/Sub, so it is **not
used**. There is also no generic HTTP `deliver` target, and delivery via an
agent-run skill proved unreliable (the local model returns text without calling
the tool — observed `tool_turns=0`).

So this repo ships a tiny **send-only platform plugin**,
`deploy/plugins/gchat_webhook`, modelled on the bundled `ntfy` adapter. It
registers `Platform("gchat_webhook")` whose `send()` POSTs `{"text": ...}` to the
space **incoming webhook URL** (`GOOGLE_CHAT_WEBHOOK_URL`). Wired as
`deliver: gchat_webhook`, the gateway delivers the full response deterministically.

This path is **one-way** (send only); there is no reverse Chat→agent channel,
which matches the agreed scope. Enable it with
`hermes plugins enable gchat_webhook-platform`.

## Verified against the installed Hermes Agent v0.17.0

Confirmed by reading the installed source (`/usr/local/lib/hermes-agent`):

- **Generic HMAC** — header `X-Webhook-Signature` = `hex(HMAC-SHA256(body))`
  (no `sha256=` prefix). `alert_push.sh` produces exactly this; openssl↔python
  interop test passes.
- **Google Chat delivery** — the native `google_chat` platform plugin only does
  the Chat REST API via a service account (needs a GCP project + Pub/Sub), so it
  is not usable here. There is no generic HTTP/webhook `deliver` target either.
  Hence the bundled `gchat_webhook` platform plugin → space incoming webhook.
  **Verified end-to-end:** a signed OEM POST produced a full ~4 KB RCA that the
  plugin delivered to the webhook URL (captured with a local HTTP listener).
- **Webhook secret** — `${VAR}` interpolation is NOT applied to platform config
  when the gateway runs under systemd (.env isn't in the process env at config
  parse time). The route `secret:` must be the literal value (config.yaml is 0600).
- **AWR truncation** — a named string field like `{awr_text}` is **not** truncated
  (`str(value)`); only `{__raw__}` (4000 chars) and dict/list fields (2000 chars)
  are. So full AWR text passes through. `awr_export.sh` still trims to ~60 KB to
  bound model cost.
- **Skills** install under `~/.hermes/skills/oracle/<name>/SKILL.md` and show as
  `enabled` in `hermes skills list`.
- **Model** is already `provider: custom` → internal OpenAI-compatible endpoint;
  this deployment leaves it untouched (don't overwrite config.yaml).

## Still a deployment decision

- **Dedup / cost control.** Enforce a severity gate + dedup on the OEM side (only
  call `alert_push.sh` for severe/new alerts), since Hermes runs the agent on
  every accepted POST.

## What was removed

The first iteration hand-rolled a FastAPI service (LLM router, pgvector store,
Google Chat client, pipeline). That duplicated Hermes' built-ins and was removed
in the pivot. Reused from it: the OEM collectors, the masking logic (now
`scripts/redact.py`), and the skill prompts (now `SKILL.md` files).
