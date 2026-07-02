"""Hermes MCP server — exposes the DDS/META store to the agent (Luồng B).

Read-only: connects to PostgreSQL as `mcp_ro` (SELECT-only). Runs as OS user
`mcp_svc` under systemd, listens on 127.0.0.1:9000 (streamable HTTP). Hermes
connects via `mcp_servers.dds.url` in config.yaml.

Config from environment (see /opt/mcp/db.env):
  PGHOST PGPORT PGUSER PGPASSWORD DDS_DB META_DB
  MCP_HOST (default 127.0.0.1) MCP_PORT (default 9000)
"""
import os
from typing import Optional

import psycopg
from mcp.server.fastmcp import FastMCP

DDS_DB = os.getenv("DDS_DB", "dds")
META_DB = os.getenv("META_DB", "meta")
_BASE = dict(
    host=os.getenv("PGHOST", "127.0.0.1"),
    port=int(os.getenv("PGPORT", "5432")),
    user=os.getenv("PGUSER", "mcp_ro"),
    password=os.getenv("PGPASSWORD", ""),
)

mcp = FastMCP("hermes-dds", host=os.getenv("MCP_HOST", "127.0.0.1"),
              port=int(os.getenv("MCP_PORT", "9000")))


def _rows(dbname: str, sql: str, params: tuple = ()) -> list[dict]:
    with psycopg.connect(dbname=dbname, **_BASE, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


@mcp.tool()
def list_instances(db_type: Optional[str] = None) -> list[dict]:
    """List monitored DB instances (optionally filtered by db_type)."""
    if db_type:
        return _rows(META_DB,
                     "SELECT name, db_type, environment, owner_team FROM db_instance "
                     "WHERE db_type=%s ORDER BY name", (db_type,))
    return _rows(META_DB,
                 "SELECT name, db_type, environment, owner_team FROM db_instance ORDER BY name")


@mcp.tool()
def recent_metrics(instance: str, metric: str, minutes: int = 60) -> list[dict]:
    """Recent rolled-up metric values for an instance (last N minutes)."""
    return _rows(DDS_DB,
                 "SELECT window_start, window_end, avg_val, max_val, min_val, last_val "
                 "FROM metric_rollup WHERE instance=%s AND metric=%s "
                 "AND window_start > now() - (%s || ' minutes')::interval "
                 "ORDER BY window_start DESC", (instance, metric, str(minutes)))


@mcp.tool()
def recent_events(instance: Optional[str] = None, severity: Optional[str] = None,
                  limit: int = 20) -> list[dict]:
    """Recent normalized DB events (OEM alerts / notable logs)."""
    where, params = [], []
    if instance:
        where.append("instance=%s"); params.append(instance)
    if severity:
        where.append("severity=%s"); params.append(severity)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(min(limit, 200))
    return _rows(DDS_DB,
                 f"SELECT instance, event_type, severity, occurred_at, source, signature, detail "
                 f"FROM db_event {clause} ORDER BY occurred_at DESC LIMIT %s", tuple(params))


@mcp.tool()
def incident_history(instance: Optional[str] = None, signature: Optional[str] = None,
                     limit: int = 10) -> list[dict]:
    """Past RCA incidents — for similar-error recall and trend context."""
    where, params = [], []
    if instance:
        where.append("instance=%s"); params.append(instance)
    if signature:
        where.append("signature=%s"); params.append(signature)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(min(limit, 100))
    return _rows(DDS_DB,
                 f"SELECT instance, signature, summary, root_cause, created_at "
                 f"FROM incident {clause} ORDER BY created_at DESC LIMIT %s", tuple(params))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
