#!/usr/bin/env bash
# gchat_send.sh — post a message to a Google Chat space via its INCOMING
# WEBHOOK url. No GCP project / service account needed — the space owner
# creates the webhook in Chat (Space -> Apps & integrations -> Webhooks).
#
# Runs on the Hermes gateway host (the agent invokes it after producing an RCA).
#
# Env:
#   GOOGLE_CHAT_WEBHOOK_URL   required — the space incoming-webhook URL
#   GCHAT_DRY_RUN=1           optional — print the payload instead of POSTing
#
# Usage:
#   gchat_send.sh "Tiêu đề" "Nội dung markdown..."
#   echo "Nội dung" | gchat_send.sh "Tiêu đề"
set -euo pipefail

: "${GOOGLE_CHAT_WEBHOOK_URL:?set GOOGLE_CHAT_WEBHOOK_URL}"

TITLE="${1:-Hermes RCA}"
if [ "${2:-}" != "" ]; then
    BODY="$2"
else
    BODY="$(cat)"   # read body from stdin
fi

# Google Chat renders a subset of markdown in `text`: *bold*, _italic_,
# `code`, lists via newlines. A simple text message is the most robust
# delivery for a one-way RCA notification.
TEXT="$(printf '*%s*\n\n%s' "$TITLE" "$BODY")"
PAYLOAD="$(jq -nc --arg t "$TEXT" '{text:$t}')"

if [ "${GCHAT_DRY_RUN:-0}" = "1" ]; then
    printf 'DRY_RUN -> %s\n%s\n' "$GOOGLE_CHAT_WEBHOOK_URL" "$PAYLOAD"
    exit 0
fi

curl -fsS -X POST "$GOOGLE_CHAT_WEBHOOK_URL" \
    -H "Content-Type: application/json; charset=UTF-8" \
    --data-binary "$PAYLOAD"
echo
