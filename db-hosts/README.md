# DB hosts — Telegraf local (Luồng B)

Each of the 30-100 DB servers runs a local **Telegraf** that scrapes localhost
and pushes metrics every 15s to the central VM's InfluxDB. Deployed at scale
with Ansible.

## Deploy

```bash
cd db-hosts/ansible
cp inventory.example.ini inventory.ini      # fill hosts + vars
# put telegraf_write_token + DB passwords in ansible-vault
ansible-playbook -i inventory.ini playbook.yml
```

- Oracle: no official Telegraf input → `exec` runs `scripts/oracle_metrics.sh`
  (SQL*Plus) emitting InfluxDB line protocol, tagged `instance=<name>`.
- Postgres/MySQL/MongoDB/SQL Server: native Telegraf inputs.
- The central-VM `telegraf_write_token` comes from InfluxDB (write-only, on the
  `metrics` bucket). Never commit it — use ansible-vault.

## Data path

Telegraf → InfluxDB (`metrics` bucket) → normalization job → DDS.`metric_rollup`
→ MCP tool `recent_metrics` → Hermes. Metrics are keyed by the `instance` tag,
which must match `meta.db_instance.name`.
