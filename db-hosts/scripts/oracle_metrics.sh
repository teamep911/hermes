#!/usr/bin/env bash
# oracle_metrics.sh — Telegraf `exec` input for Oracle (no official input plugin).
# Emits InfluxDB line protocol on stdout; Telegraf tags/ships to InfluxDB.
# Runs on each Oracle DB host (installed by the Ansible playbook).
#
# Env: ORACLE_HOME, ORACLE_SID, and INSTANCE_NAME (logical name, e.g. ORCLPROD).
set -euo pipefail
INSTANCE="${INSTANCE_NAME:-${ORACLE_SID:-unknown}}"

sqlplus -s / as sysdba <<'SQL' 2>/dev/null | awk -v inst="$INSTANCE" '
/^METRIC/ { print "oracle,instance=" inst " " $2 "=" $3 }
'
SET HEADING OFF FEEDBACK OFF PAGESIZE 0 LINESIZE 200
SELECT 'METRIC active_sessions ' || COUNT(*) || 'i' FROM v$session WHERE status='ACTIVE';
SELECT 'METRIC blocking_sessions ' || COUNT(*) || 'i' FROM v$session WHERE blocking_session IS NOT NULL;
SELECT 'METRIC total_sessions ' || COUNT(*) || 'i' FROM v$session;
SELECT 'METRIC db_cpu_per_sec ' || ROUND(NVL(value,0),2) FROM v$sysmetric WHERE metric_name='CPU Usage Per Sec' AND ROWNUM=1;
SELECT 'METRIC hard_parse_per_sec ' || ROUND(NVL(value,0),2) FROM v$sysmetric WHERE metric_name='Hard Parse Count Per Sec' AND ROWNUM=1;
SQL
