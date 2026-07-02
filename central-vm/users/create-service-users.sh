#!/usr/bin/env bash
# create-service-users.sh — per-service OS isolation on the central VM.
# Run as root once. Each service runs under its own unprivileged user; root is
# only used for installation (architecture doc §3.3).
set -euo pipefail

create() {
    local u="$1" home="$2"
    if id "$u" &>/dev/null; then
        echo "user $u exists"
    else
        useradd --system --create-home --home-dir "$home" --shell /usr/sbin/nologin "$u"
        echo "created $u ($home)"
    fi
}

# DDS/META owner + normalization job
create dds_db   /opt/dds
# MCP server (DB access is SELECT-only via a dedicated Postgres role)
create mcp_svc  /opt/mcp
# n8n workflow engine
create n8n_svc  /opt/n8n
# Hermes Agent (currently runs as root — migrate here; see central-vm/hermes/)
create hermes_svc /opt/hermes

install -d -o dds_db  -g dds_db  -m 0750 /opt/dds
install -d -o mcp_svc -g mcp_svc -m 0750 /opt/mcp
install -d -o n8n_svc -g n8n_svc -m 0750 /opt/n8n
echo "service users ready"
