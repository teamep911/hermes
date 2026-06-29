#!/usr/bin/env bash
# alert_push.sh — OEM-side dispatcher.
# Gathers the alert + enrichment (sessions, AWR), builds the JSON payload,
# signs it with HMAC-SHA256 and POSTs it to the Hermes webhook.
#
# OEM corrective-action / notification method calls this with the alert
# fields as arguments or environment variables.
#
# Config via environment (no secrets in this file):
#   HERMES_URL          e.g. https://<hermes-host>/webhook/oem   (placeholder)
#   AGENT_WEBHOOK_SECRET shared HMAC secret (same as Hermes side)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${HERMES_URL:?set HERMES_URL}"
: "${AGENT_WEBHOOK_SECRET:?set AGENT_WEBHOOK_SECRET}"

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

# HMAC-SHA256 over the raw body.
SIG="sha256=$(printf '%s' "$PAYLOAD" \
    | openssl dgst -sha256 -hmac "$AGENT_WEBHOOK_SECRET" -binary \
    | xxd -p -c 256)"

curl -fsS -X POST "$HERMES_URL" \
    -H "Content-Type: application/json" \
    -H "X-Hermes-Signature: $SIG" \
    --data-binary "$PAYLOAD"
echo
