"""Normalization job (Luồng B): InfluxDB metrics -> DDS.metric_rollup.

Runs on a systemd timer as OS user dds_db. Queries InfluxDB for the last
window, aggregates per (instance, metric), and upserts one rollup row per
metric per window into the DDS DB. Idempotent via the UNIQUE(instance, metric,
window_start) constraint.

Env (from /opt/dds/db.env): INFLUX_URL INFLUX_ORG INFLUX_BUCKET INFLUX_TOKEN
PGHOST PGPORT PGUSER PGPASSWORD  (writes to the `dds` database).
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

import psycopg

WINDOW_MIN = int(os.getenv("NORMALIZE_WINDOW_MIN", "1"))
INFLUX_URL = os.getenv("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_ORG = os.getenv("INFLUX_ORG", "central")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "metrics")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")

# Flux: for the last window, aggregate each series to mean/max/min/last, keyed
# by the `instance` (or host) tag and the field name.
FLUX = f'''
data = from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -{WINDOW_MIN}m)
  |> filter(fn: (r) => exists r._value and (exists r.instance or exists r.host))
mean = data |> mean()  |> map(fn: (r) => ({{ r with agg: "avg" }}))
mx   = data |> max()   |> map(fn: (r) => ({{ r with agg: "max" }}))
mn   = data |> min()   |> map(fn: (r) => ({{ r with agg: "min" }}))
lst  = data |> last()  |> map(fn: (r) => ({{ r with agg: "last" }}))
union(tables: [mean, mx, mn, lst])
  |> keep(columns: ["_measurement", "_field", "instance", "host", "_value", "agg"])
'''


def query_influx() -> list[dict]:
    if not INFLUX_TOKEN:
        return []
    req = urllib.request.Request(
        f"{INFLUX_URL}/api/v2/query?org={INFLUX_ORG}",
        data=json.dumps({"query": FLUX, "type": "flux"}).encode(),
        headers={"Authorization": f"Token {INFLUX_TOKEN}",
                 "Content-Type": "application/json",
                 "Accept": "application/csv"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read().decode()
    # Parse annotated CSV
    rows, header = [], None
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        cells = line.split(",")
        if header is None:
            header = cells
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def aggregate(rows: list[dict]) -> dict:
    """(instance, metric) -> {avg,max,min,last}."""
    out: dict = {}
    for r in rows:
        inst = r.get("instance") or r.get("host")
        field = r.get("_field") or r.get("_measurement")
        agg = r.get("agg")
        val = r.get("_value")
        if not inst or not field or agg is None or val in (None, ""):
            continue
        try:
            v = float(val)
        except ValueError:
            continue
        out.setdefault((inst, field), {})[agg] = v
    return out


def main() -> None:
    now = datetime.now(timezone.utc)
    agg = aggregate(query_influx())
    if not agg:
        print("normalize: no data this window")
        return
    win_start = now.replace(second=0, microsecond=0)
    with psycopg.connect(
        dbname="dds", host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", "5432")), user=os.getenv("PGUSER", "dds_db"),
        password=os.getenv("PGPASSWORD", ""), connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            for (inst, metric), a in agg.items():
                cur.execute(
                    """INSERT INTO metric_rollup
                       (instance, metric, window_start, window_end, avg_val, max_val, min_val, last_val)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (instance, metric, window_start) DO UPDATE SET
                         avg_val=EXCLUDED.avg_val, max_val=EXCLUDED.max_val,
                         min_val=EXCLUDED.min_val, last_val=EXCLUDED.last_val""",
                    (inst, metric, win_start, now,
                     a.get("avg"), a.get("max"), a.get("min"), a.get("last")),
                )
        conn.commit()
    print(f"normalize: upserted {len(agg)} rollup row(s)")


if __name__ == "__main__":
    main()
