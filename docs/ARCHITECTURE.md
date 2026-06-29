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

## Open items to confirm against the installed Hermes version

- **`deliver` key for Google Chat.** Confirm the exact delivery identifier (and
  whether a `space`/channel must be passed in `deliver_extra`) for the webhook
  route. Google Chat is provisioned via `hermes gateway setup`; the route may
  instead post to `GOOGLE_CHAT_HOME_CHANNEL`.
- **Large AWR payloads.** `{__raw__}` is truncated at ~4000 chars; we reference
  named fields (`{awr_text}`) instead. Confirm named fields are not truncated; if
  they are, have the skill pull AWR in chunks or pre-summarise on the OEM host
  (`awr_export.sh` already trims to ~60 KB).
- **Dedup / cost control.** The legacy design had a severity gate + dedup window.
  Decide whether to enforce these on the OEM side (only call `alert_push.sh` for
  severe/new alerts) or via Hermes config.

## What was removed

The first iteration hand-rolled a FastAPI service (LLM router, pgvector store,
Google Chat client, pipeline). That duplicated Hermes' built-ins and was removed
in the pivot. Reused from it: the OEM collectors, the masking logic (now
`scripts/redact.py`), and the skill prompts (now `SKILL.md` files).
