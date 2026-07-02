#!/usr/bin/env bash
# awr_export.sh — generate a text AWR report for the last N snapshots.
# Runs on the OEM/DB host. Output is captured by alert_push.sh.
#
# Usage: awr_export.sh [num_snapshots]   (default: last 2 snapshots)
set -euo pipefail

NUM_SNAPS="${1:-2}"
OUT="$(mktemp /tmp/awr_XXXXXX.txt)"
trap 'rm -f "$OUT"' EXIT

sqlplus -s / as sysdba <<SQL >/dev/null
SET HEADING OFF FEEDBACK OFF VERIFY OFF PAGESIZE 0 LINESIZE 200 TRIMSPOOL ON
SPOOL ${OUT}
DECLARE
    l_dbid     NUMBER;
    l_inst     NUMBER;
    l_end      NUMBER;
    l_begin    NUMBER;
BEGIN
    SELECT dbid INTO l_dbid FROM v\$database;
    SELECT instance_number INTO l_inst FROM v\$instance;
    SELECT MAX(snap_id) INTO l_end FROM dba_hist_snapshot WHERE dbid = l_dbid;
    l_begin := l_end - ${NUM_SNAPS};
    FOR r IN (
        SELECT output FROM TABLE(
            dbms_workload_repository.awr_report_text(
                l_dbid, l_inst, l_begin, l_end))
    ) LOOP
        dbms_output.put_line(r.output);
    END LOOP;
END;
/
SPOOL OFF
SQL

# Trim to a sane size for the LLM context window (head of the report holds
# the load profile + top wait events + top SQL).
head -c 60000 "$OUT"
