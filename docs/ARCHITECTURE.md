# Architecture

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
| LLM analysis | `model.provider: anthropic` with your own key |
| Google Chat | Native channel (Pub/Sub inbound + Chat REST outbound) |
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
   `prompt` template (`deploy/config.yaml`) from payload fields.
5. **Reason (Hermes).** The route loads the three Oracle skills; the agent picks
   one by its "When to Use" section and calls your Claude model. Hermes memory
   supplies similar past incidents automatically.
6. **Deliver.** The analysis is sent to the Google Chat space.

## Skill selection

The route loads all three skills and lets the agent choose:
- lock / blocking / session dump → `oracle-rca`
- CPU/IO/memory threshold with AWR → `awr-summary`
- everything else → `alert-triage`

## Google Chat is bidirectional (no extra work)

Hermes' Google Chat channel uses **Cloud Pub/Sub pull** for inbound and the
**Chat REST API** for outbound via a service account — no public endpoint needed.
The earlier "incoming-webhook is send-only" limitation does not apply here: with
Hermes, slash commands / replies from Chat back to the agent work out of the box
once `hermes gateway setup` is run.

## Verified against the installed Hermes Agent v0.17.0

Confirmed by reading the installed source (`/usr/local/lib/hermes-agent`):

- **Generic HMAC** — header `X-Webhook-Signature` = `hex(HMAC-SHA256(body))`
  (no `sha256=` prefix). `alert_push.sh` produces exactly this; openssl↔python
  interop test passes.
- **`deliver: google_chat`** — valid. Google Chat is a registered platform plugin
  (`Platform("google_chat")`); webhook delivery routes cross-platform to
  `deliver_extra.chat_id`, falling back to `GOOGLE_CHAT_HOME_CHANNEL`. The plugin
  must be connected (its `GOOGLE_CHAT_*` env set + gateway running).
- **AWR truncation** — a named string field like `{awr_text}` is **not** truncated
  (`str(value)`); only `{__raw__}` (4000 chars) and dict/list fields (2000 chars)
  are. So full AWR text passes through. `awr_export.sh` still trims to ~60 KB to
  bound model cost.
- **`${VAR}` interpolation** in config.yaml works (`_expand_env_vars`), so
  `secret: ${WEBHOOK_SECRET}` resolves from `~/.hermes/.env`.
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
