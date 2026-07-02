---
name: oracle-rca
description: Root-cause Oracle locks and blocking sessions
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [oracle, rca, locks, blocking, dba]
    category: oracle
---
# Oracle RCA — Locks & Blocking Sessions

## When to Use
The alert is a lock / blocking / application-lock / session problem and a
session+lock dump is supplied. Use this to find the blocking chain, identify the
holder, and recommend the safest remediation.

## Procedure
1. Parse the session/lock dump. Build the blocking tree: which `SID` blocks which,
   and find the **root holder** (a session with `blocking_session` empty that
   others wait on).
2. Identify the locked objects and lock modes.
3. State:
   - the blocking chain (holder → waiters)
   - most likely root cause (long transaction, uncommitted DML, app deadlock, etc.)
   - operational impact (how many sessions/seconds waiting)
   - remediation — **confirm before killing**: first a read-only verification, then
     the kill statement only if confirmed
   - confirm/cleanup commands
4. **Answer in Vietnamese.**

## Inputs
Redacted placeholders (`<IP_1>`, `<HOST_2>`, …) are opaque identifiers; keep them
verbatim. The dump fields: `sid`, `serial`, `username`, `status`, `machine`,
`program`, `blocking_session`, `event`, `wait_s`, plus locked objects.

## Useful commands (reference)
- Confirm the holder is still active before acting:
  `SELECT sid, serial#, status, last_call_et FROM v$session WHERE sid = :sid;`
- Kill (only after confirmation):
  `ALTER SYSTEM KILL SESSION '<sid>,<serial>' IMMEDIATE;`

## Pitfalls
- Never recommend killing the **waiter** — kill the **holder** at the root of the
  chain.
- Do not kill background/SYS sessions.
- If the holder is an application connection pool member, recommend coordinating
  with the app team rather than a blind kill.

## Verification
Re-run the blocking query after remediation to confirm the chain cleared.
