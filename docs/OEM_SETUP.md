# OEM host setup (fresh machine)

The OEM/DB host only collects data, redacts it, and POSTs a signed alert to the
Hermes gateway. No agent, model or database runs here.

## 1. Install dependencies

```bash
# Oracle Linux / RHEL 9
sudo dnf install -y curl openssl gawk jq python3
# (sqlplus comes with the Oracle DB/Client install already present on this host)
```

Required: `bash`, `curl`, `openssl`, `awk`, `jq`, `python3`.
For AWR/session enrichment: `sqlplus` reachable as `/ as sysdba`.

## 2. Deploy the scripts

```bash
sudo mkdir -p /opt/hermes-oem
sudo cp scripts/{alert_push.sh,awr_export.sh,check_session.sh,redact.py,oem_notify.sh,preflight.sh} /opt/hermes-oem/
sudo chmod +x /opt/hermes-oem/*.sh /opt/hermes-oem/redact.py
```

## 3. Configure the environment

```bash
sudo cp scripts/oem.env.example /etc/hermes-oem.env
sudo chmod 600 /etc/hermes-oem.env
sudo vi /etc/hermes-oem.env     # set HERMES_URL, WEBHOOK_SECRET (== gateway side),
                                # MASK_TERMS, ORACLE_HOME, ORACLE_SID
```

`WEBHOOK_SECRET` **must** match the `oem-alert` route secret on the Hermes side.

## 4. Preflight

```bash
source /etc/hermes-oem.env
/opt/hermes-oem/preflight.sh
```

Confirms tools, Oracle env, gateway TCP reachability, HMAC interop, and masking.
Fix every `FAIL` before going live.

## 5. Manual end-to-end test

```bash
source /etc/hermes-oem.env
ALERT_TYPE=lock TARGET_NAME=ORCLPROD SEVERITY=critical \
MESSAGE="ORA-00060 deadlock detected" \
  /opt/hermes-oem/alert_push.sh
```

A `200` from curl means Hermes accepted the signed payload; the analysis lands in
the configured Google Chat space.

## 6. Wire into OEM

Register `oem_notify.sh` as an **OS Command notification method** in OEM
(Setup → Notifications → Methods). OEM passes event variables (e.g. `TARGET_NAME`,
`SEVERITY`, `MESSAGE`, `METRIC_COLUMN`, `VALUE`); `oem_notify.sh` maps them onto
`alert_push.sh`. Adjust the variable names to your OEM release.

Apply it to the incident rules you want routed (threshold breaches, lock/blocking
alerts, etc.).

## Cost / noise control (recommended)

Hermes runs the agent on every accepted POST, so gate at the source: only attach
`oem_notify.sh` to rules at/above the severity you care about, and let OEM's own
notification de-duplication suppress repeats. This keeps model calls bounded.
