---
name: awr-summary
description: Summarise an Oracle AWR report into actionable findings
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [oracle, awr, performance, tuning]
    category: oracle
---
# AWR Summary

## When to Use
A CPU/IO/memory/wait threshold alert arrives with an AWR text report attached.
Use this to turn the AWR numbers into a short, actionable performance conclusion.

## Procedure
1. From the AWR text, extract and report:
   - **Load profile** anomalies (DB time/s, logical/physical reads, hard parses)
   - **Top wait events** (and what they imply — I/O, contention, commits, etc.)
   - **Top SQL** by elapsed/CPU — identify the dominant statement(s)
   - any obvious single bottleneck
2. Translate numbers into a one-paragraph conclusion: what is the system
   bottlenecked on and the most likely cause.
3. Give ordered tuning recommendations (safest/cheapest first) and the commands
   or views to dig deeper (`v$active_session_history`, `dbms_xplan`, etc.).
4. **Answer in Vietnamese.**

## Inputs
Redacted placeholders (`<IP_1>`, `<HOST_2>`, …) are opaque; keep verbatim. The AWR
text may be trimmed to its head section (load profile + top waits + top SQL).

## Pitfalls
- A high wait event is not automatically the root cause — correlate with the load
  profile before concluding.
- If the report is truncated and a needed section is missing, say so explicitly
  rather than guessing.

## Verification
Recommendations should name the specific SQL_ID / wait event / metric they target
so the DBA can validate the impact afterwards.
