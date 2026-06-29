---
name: notify-google-chat
description: Send the finished RCA to the Google Chat space
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [oracle, notify, google-chat, delivery]
    category: oracle
    requires_toolsets: [terminal]
---
# Notify Google Chat

## When to Use
Always run this as the FINAL step after analysing an OEM Oracle alert
(alert-triage / oracle-rca / awr-summary), to deliver the result to the team's
Google Chat space. Delivery uses the space's incoming webhook — no GCP project
needed.

## Procedure
1. Compose the final notification text in Vietnamese: a one-line title plus the
   RCA body (summary, root cause, impact, actions, check commands).
2. Deliver it by running the bundled script (it reads
   `GOOGLE_CHAT_WEBHOOK_URL` from the environment):

   ```bash
   "${HERMES_SKILL_DIR}/scripts/gchat_send.sh" "<title>" "<rca markdown body>"
   ```

   Or pipe the body on stdin:

   ```bash
   echo "<rca body>" | "${HERMES_SKILL_DIR}/scripts/gchat_send.sh" "<title>"
   ```
3. Report whether delivery succeeded (the script prints the Chat API response).

## Pitfalls
- Do not skip this step — analysis without delivery leaves the team unaware.
- Keep placeholders (`<IP_1>`, `<HOST_2>`) verbatim; they are already redacted.
- The body is sent as Google Chat text markdown (`*bold*`, `` `code` ``,
  newlines). Do not embed raw HTML.

## Verification
A successful POST returns a JSON message object from `chat.googleapis.com`. If the
script errors, surface the error rather than claiming the alert was delivered.
