"""Skill: deep Oracle root-cause analysis using session/lock context."""
from __future__ import annotations

from .base import Skill, register


@register
class RcaOracleSkill(Skill):
    name = "rca_oracle"

    def system_prompt(self) -> str:
        return (
            "You are Hermes, a senior Oracle DBA. Perform root-cause analysis "
            "for database incidents (locks, blocking sessions, app locks, "
            "resource contention). Use the session/lock dump to identify the "
            "blocking chain and the holder. Recommend the safest remediation "
            "first (e.g. confirm before killing a session). Answer in Vietnamese."
        )

    def user_prompt(self, alert: dict, memory_block: str) -> str:
        lines = [
            "## Incident",
            f"- type: {alert.get('alert_type')}",
            f"- target: {alert.get('target_name')}",
            f"- metric: {alert.get('metric_name')} = {alert.get('metric_value')}",
            f"- severity: {alert.get('severity')}",
            f"- message: {alert.get('message')}",
            "",
            "## Session / lock dump (redacted)",
            alert.get("session_text") or "(none provided)",
        ]
        if memory_block:
            lines += ["", "## Similar past incidents", memory_block]
        return "\n".join(lines)
