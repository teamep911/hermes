#!/usr/bin/env bash
# alert_push.sh — OEM-side dispatcher.
# Gathers the alert + enrichment (sessions, AWR), REDACTS sensitive data on
# this host, signs the body with HMAC-SHA256 and POSTs it to the Hermes Agent
# webhook adapter (route "oem-alert").
#
# OEM corrective-action / notification method calls this with the alert
# fields as arguments or environment variables.
#
# Config via environment (no secrets in this file):
#   HERMES_URL      e.g. http://<hermes-host>:8644/webhooks/oem-alert
#   WEBHOOK_SECRET  shared HMAC secret (same as the route `secret` in config.yaml)
#   MASK_TERMS      optional comma-separated exact terms to mask (e.g. SID,schema)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${HERMES_URL:?set HERMES_URL}"
: "${WEBHOOK_SECRET:?set WEBHOOK_SECRET}"
MASK_TERMS="${MASK_TERMS:-}"

ALERT_TYPE="${ALERT_TYPE:-threshold}"
TARGET_NAME="${TARGET_NAME:-unknown}"
METRIC_NAME="${METRIC_NAME:-}"
METRIC_VALUE="${METRIC_VALUE:-}"
SEVERITY="${SEVERITY:-warning}"
MESSAGE="${MESSAGE:-}"
EVENT_TIME="$(date -Is)"

# Enrichment — only collect what's relevant to the alert type.
SESSION_TEXT=""
AWR_TEXT=""
case "$ALERT_TYPE" in
    lock|block|session)
        SESSION_TEXT="$(bash "$SCRIPT_DIR/check_session.sh" 2>/dev/null || true)"
        ;;
    threshold|custom)
        if [[ "$METRIC_NAME" =~ (cpu|io|memory|wait) ]]; then
            AWR_TEXT="$(bash "$SCRIPT_DIR/awr_export.sh" 2 2>/dev/null || true)"
        fi
        ;;
esac

# --- Redact sensitive data ON THIS HOST before anything leaves it. ---
# IPs, hostnames, domains, secrets become opaque placeholders. The agent and
# the LLM only ever see the masked form.
REDACT=(python3 "$SCRIPT_DIR/redact.py")
[[ -n "$MASK_TERMS" ]] && REDACT+=(--terms "$MASK_TERMS")
MESSAGE="$(printf '%s' "$MESSAGE" | "${REDACT[@]}")"
SESSION_TEXT="$(printf '%s' "$SESSION_TEXT" | "${REDACT[@]}")"
AWR_TEXT="$(printf '%s' "$AWR_TEXT" | "${REDACT[@]}")"
METRIC_VALUE="$(printf '%s' "$METRIC_VALUE" | "${REDACT[@]}")"

# Build JSON payload safely with jq.
PAYLOAD="$(jq -nc \
    --arg alert_type "$ALERT_TYPE" \
    --arg target_name "$TARGET_NAME" \
    --arg metric_name "$METRIC_NAME" \
    --arg metric_value "$METRIC_VALUE" \
    --arg severity "$SEVERITY" \
    --arg message "$MESSAGE" \
    --arg event_time "$EVENT_TIME" \
    --arg session_text "$SESSION_TEXT" \
    --arg awr_text "$AWR_TEXT" \
    '{alert_type:$alert_type, target_name:$target_name,
      metric_name:($metric_name|select(.!="")),
      metric_value:($metric_value|select(.!="")),
      severity:$severity, message:$message, event_time:$event_time,
      session_text:($session_text|select(.!="")),
      awr_text:($awr_text|select(.!=""))}')"

# Generic Hermes webhook HMAC: header "X-Webhook-Signature" = raw hex digest.
# `awk '{print $NF}'` grabs the hex from openssl's "...= <hex>" output, so we
# don't depend on xxd being installed on the OEM host.
SIG="$(printf '%s' "$PAYLOAD" \
    | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" \
    | awk '{print $NF}')"

curl -fsS -X POST "$HERMES_URL" \
    -H "Content-Type: application/json" \
    -H "X-Webhook-Signature: $SIG" \
    --data-binary "$PAYLOAD"
echo
