#!/usr/bin/env bash
# preflight.sh — verify a fresh OEM host can run the alert dispatcher.
# Checks required tools, the Oracle environment, gateway connectivity, and does
# a local HMAC self-test. Read-only; makes no changes.
#
# Usage:  source /etc/hermes-oem.env && ./preflight.sh
set -uo pipefail

ok=0; warn=0; err=0
pass(){ printf '  \033[32mOK\033[0m   %s\n' "$1"; ok=$((ok+1)); }
note(){ printf '  \033[33mWARN\033[0m %s\n' "$1"; warn=$((warn+1)); }
fail(){ printf '  \033[31mFAIL\033[0m %s\n' "$1"; err=$((err+1)); }

echo "== Required tools =="
for t in bash curl openssl awk jq python3; do
    if command -v "$t" >/dev/null 2>&1; then pass "$t -> $(command -v "$t")"
    else fail "$t missing (install it)"; fi
done

echo "== Oracle environment (for AWR / session collectors) =="
[ -n "${ORACLE_HOME:-}" ] && pass "ORACLE_HOME=$ORACLE_HOME" || note "ORACLE_HOME unset"
[ -n "${ORACLE_SID:-}" ]  && pass "ORACLE_SID=$ORACLE_SID"   || note "ORACLE_SID unset"
if command -v sqlplus >/dev/null 2>&1; then
    pass "sqlplus -> $(command -v sqlplus)"
    if echo 'set head off feedback off; select 1 from dual;' | sqlplus -s / as sysdba 2>/dev/null | grep -q 1; then
        pass "sqlplus '/ as sysdba' connects"
    else
        note "sqlplus present but '/ as sysdba' did not return (check OS auth / env)"
    fi
else
    note "sqlplus not in PATH (collectors will send alerts without AWR/session data)"
fi

echo "== Gateway config =="
[ -n "${HERMES_URL:-}" ]     && pass "HERMES_URL=$HERMES_URL"   || fail "HERMES_URL unset (set it in oem.env)"
[ -n "${WEBHOOK_SECRET:-}" ] && pass "WEBHOOK_SECRET is set"    || fail "WEBHOOK_SECRET unset (set it in oem.env)"

echo "== Gateway connectivity =="
if [ -n "${HERMES_URL:-}" ]; then
    host_port="$(printf '%s' "$HERMES_URL" | sed -E 's#^https?://([^/]+)/.*#\1#')"
    host="${host_port%%:*}"; port="${host_port##*:}"; [ "$port" = "$host" ] && port=80
    if timeout 5 bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then
        pass "TCP reachable: $host:$port"
    else
        fail "cannot reach $host:$port (firewall / route / gateway down?)"
    fi
fi

echo "== HMAC self-test =="
if [ -n "${WEBHOOK_SECRET:-}" ]; then
    body='{"ping":"preflight"}'
    a=$(printf '%s' "$body" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $NF}')
    b=$(WEBHOOK_SECRET="$WEBHOOK_SECRET" BODY="$body" python3 -c "import os,hmac,hashlib;print(hmac.new(os.environ['WEBHOOK_SECRET'].encode(),os.environ['BODY'].encode(),hashlib.sha256).hexdigest())")
    [ "$a" = "$b" ] && pass "openssl/python HMAC agree" || fail "HMAC mismatch ($a vs $b)"
fi

echo "== Masking self-test =="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$(printf 'host 10.1.2.3 db.example.com pwd=secret' | python3 "$SCRIPT_DIR/redact.py" 2>/dev/null || true)"
if [ -n "$out" ] && ! printf '%s' "$out" | grep -qE '10\.1\.2\.3|example\.com|secret'; then
    pass "redact.py masks IP/domain/secret"
else
    fail "redact.py did not mask correctly: $out"
fi

echo
echo "Summary: $ok OK, $warn WARN, $err FAIL"
[ "$err" -eq 0 ] && echo "Preflight passed." || { echo "Fix FAIL items before going live."; exit 1; }
