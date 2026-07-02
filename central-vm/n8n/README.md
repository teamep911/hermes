# n8n — NOT installed on this host

Per deployment decision, n8n does **not** run on the central VM. It is hosted
separately (its own VM/host or an existing n8n instance). Hermes reaches it over
HTTP when it needs to trigger a workflow.

This directory keeps the deployment artefacts for wherever n8n does run:

- `n8n.service` — systemd unit (adjust `User`, bind host/port to that host).

## Wiring Hermes → n8n (when n8n exists)

Hermes triggers n8n via an n8n **Webhook node**. Point Hermes at the webhook URL
of the target workflow (e.g. from a skill or a gateway hook), no plugin needed:

```
POST https://<n8n-host>/webhook/<path>
```

Keep the n8n webhook URL/secret out of the repo (in `~/.hermes/.env`).
The `n8n_svc` OS user created by `central-vm/users/create-service-users.sh` is
only needed on the host that actually runs n8n; it is unused on the central VM.
