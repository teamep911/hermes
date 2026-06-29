#!/usr/bin/env bash
# oem_notify.sh — example Oracle Enterprise Manager notification wrapper.
#
# Register this as an OS Command notification method in OEM. OEM exports the
# event details as environment variables (names vary by OEM version); this
# wrapper maps them onto the variables alert_push.sh expects, then dispatches.
#
# Map / adjust the OEM_* variable names to your OEM release. Common ones:
#   TARGET_NAME, SEVERITY, MESSAGE, METRIC_COLUMN, VALUE, EVENT_TYPE ...
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load gateway URL + secret + Oracle env (kept out of VCS).
# shellcheck disable=SC1091
source /etc/hermes-oem.env

# --- Map OEM-provided variables -> alert_push.sh inputs ---
# Classify the alert so the agent picks the right skill.
case "${MESSAGE:-}${EVENT_TYPE:-}" in
    *[Ll]ock*|*ORA-00060*|*blocking*) export ALERT_TYPE="lock" ;;
    *[Cc][Pp][Uu]*|*I/O*|*[Mm]emory*) export ALERT_TYPE="threshold" ;;
    *)                                 export ALERT_TYPE="custom" ;;
esac

export TARGET_NAME="${TARGET_NAME:-${OEM_TARGET_NAME:-unknown}}"
export METRIC_NAME="${METRIC_COLUMN:-${OEM_METRIC:-}}"
export METRIC_VALUE="${VALUE:-${OEM_VALUE:-}}"
export SEVERITY="$(printf '%s' "${SEVERITY:-warning}" | tr '[:upper:]' '[:lower:]')"
export MESSAGE="${MESSAGE:-${OEM_MESSAGE:-}}"

exec "$SCRIPT_DIR/alert_push.sh"
