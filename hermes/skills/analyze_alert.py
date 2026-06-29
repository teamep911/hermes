"""Skill: general alert triage / analysis."""
from __future__ import annotations

from .base import Skill, register


@register
class AnalyzeAlertSkill(Skill):
    name = "analyze_alert"

    def system_prompt(self) -> str:
        return (
            "You are Hermes, an Oracle/Linux SRE assistant. You triage OEM "
            "(Oracle Enterprise Manager) alerts. Given an alert and any "
            "similar past incidents, classify the problem, state the most "
            "likely root cause, the impact, and concrete next actions. Be "
            "precise and operational. Answer in Vietnamese."
        )

    def user_prompt(self, alert: dict, memory_block: str) -> str:
        lines = [
            "## Alert",
            f"- type: {alert.get('alert_type')}",
            f"- target: {alert.get('target_name')} ({alert.get('target_type')})",
            f"- metric: {alert.get('metric_name')} = {alert.get('metric_value')}",
            f"- severity: {alert.get('severity')}",
            f"- message: {alert.get('message')}",
            f"- event_time: {alert.get('event_time')}",
        ]
        if memory_block:
            lines += ["", "## Similar past incidents", memory_block]
        return "\n".join(lines)
