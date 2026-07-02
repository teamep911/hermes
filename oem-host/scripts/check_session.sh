#!/usr/bin/env bash
# check_session.sh — dump blocking/locking session info from Oracle.
# Runs on the OEM/DB host. Output is captured by alert_push.sh and sent
# to Hermes (which redacts it before any LLM call).
#
# Requires: ORACLE_HOME / ORACLE_SID set, sqlplus in PATH.
set -euo pipefail

sqlplus -s / as sysdba <<'SQL'
SET PAGESIZE 200 LINESIZE 200 FEEDBACK OFF HEADING ON TRIMSPOOL ON
PROMPT === BLOCKING TREE ===
SELECT s.sid,
       s.serial# AS serial,
       s.username,
       s.status,
       s.machine,
       s.program,
       s.blocking_session,
       s.event,
       s.seconds_in_wait AS wait_s
FROM   v$session s
WHERE  s.blocking_session IS NOT NULL
    OR s.sid IN (SELECT blocking_session FROM v$session WHERE blocking_session IS NOT NULL)
ORDER BY s.blocking_session NULLS FIRST, s.sid;

PROMPT === LOCKED OBJECTS ===
SELECT l.session_id AS sid,
       o.object_name,
       o.object_type,
       DECODE(l.locked_mode,0,'none',1,'null',2,'row-S',3,'row-X',
              4,'share',5,'S/Row-X',6,'exclusive',TO_CHAR(l.locked_mode)) AS mode
FROM   v$locked_object l
JOIN   dba_objects o ON o.object_id = l.object_id
ORDER BY l.session_id;
SQL
