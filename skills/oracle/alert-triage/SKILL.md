---
name: alert-triage
description: Triage OEM Oracle/Linux alerts and propose next actions
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [oracle, oem, monitoring, sre]
    category: oracle
---
# Alert Triage (OEM)

## When to Use
A generic OEM alert arrives (tablespace, listener, agent, threshold) that is
not specifically a lock/blocking or AWR-performance case. Use this to classify
the problem, state the most likely cause, the impact, and concrete next steps.

## Procedure
1. Read the alert fields: `alert_type`, `target_name`, `metric_name`,
   `metric_value`, `severity`, `message`, `event_time`.
2. If past similar incidents are provided, use them to bias the diagnosis and
   reuse remediations that worked.
3. Classify the problem in one line, then give:
   - root cause (most likely)
   - operational impact
   - ordered, concrete remediation steps (safest first)
   - SQL/shell commands to confirm the diagnosis
4. Keep the answer short and operational. **Answer in Vietnamese.**

## Inputs
Placeholders like `<IP_1>`, `<HOST_2>`, `<DOMAIN_1>` are redacted real values —
treat them as opaque identifiers and keep them verbatim in the output. Never ask
to unmask them.

## Pitfalls
- Do not invent commands or object names that are not implied by the alert.
- Do not recommend destructive actions (kill/restart/drop) as the first step —
  always confirm with a read-only check first.

## Verification
Every recommendation must be backed by a check command the operator can run to
confirm before acting.
