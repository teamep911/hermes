"""Skill: summarise an AWR report and surface performance hotspots."""
from __future__ import annotations

from .base import Skill, register


@register
class AwrSummarySkill(Skill):
    name = "awr_summary"

    def system_prompt(self) -> str:
        return (
            "You are Hermes, an Oracle performance engineer. Summarise the "
            "provided AWR report: highlight top wait events, load profile "
            "anomalies, top SQL by elapsed/CPU, and any obvious bottleneck. "
            "Translate the numbers into an actionable conclusion. Answer in "
            "Vietnamese."
        )

    def user_prompt(self, alert: dict, memory_block: str) -> str:
        lines = [
            "## Context",
            f"- target: {alert.get('target_name')}",
            f"- triggered by: {alert.get('alert_type')} / {alert.get('metric_name')}",
            "",
            "## AWR report (redacted)",
            alert.get("awr_text") or "(none provided)",
        ]
        if memory_block:
            lines += ["", "## Similar past incidents", memory_block]
        return "\n".join(lines)
