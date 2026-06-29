"""Render an RcaResult into markdown and a Google Chat card payload."""
from __future__ import annotations

from .models import OemAlert, RcaResult

_SEVERITY_EMOJI = {
    "info": "ℹ️",
    "warning": "⚠️",
    "critical": "🔴",
    "fatal": "💥",
}


def to_markdown(alert: OemAlert, rca: RcaResult) -> str:
    emoji = _SEVERITY_EMOJI.get(alert.severity, "⚠️")
    lines = [
        f"{emoji} *[{alert.severity.upper()}] {alert.target_name}* — {alert.alert_type}",
        "",
        f"*Tóm tắt:* {rca.summary}",
    ]
    if rca.root_cause:
        lines.append(f"*Nguyên nhân:* {rca.root_cause}")
    if rca.impact:
        lines.append(f"*Ảnh hưởng:* {rca.impact}")
    if rca.recommended_actions:
        lines.append("*Hành động đề xuất:*")
        lines += [f"  {i}. {a}" for i, a in enumerate(rca.recommended_actions, 1)]
    if rca.check_commands:
        lines.append("*Lệnh kiểm tra:*")
        lines += [f"  • `{c}`" for c in rca.check_commands]
    footer = f"_skill: {rca.skill} · model: {rca.provider_used}/{rca.model_used} · confidence: {rca.confidence}_"
    if rca.similar_incidents:
        footer += f" · similar: {', '.join('#' + str(i) for i in rca.similar_incidents)}"
    lines += ["", footer]
    return "\n".join(lines)


def to_google_chat_card(alert: OemAlert, rca: RcaResult) -> dict:
    """Cards v2 payload for the Google Chat incoming webhook."""
    emoji = _SEVERITY_EMOJI.get(alert.severity, "⚠️")
    widgets: list[dict] = [
        {"textParagraph": {"text": f"<b>Tóm tắt:</b> {rca.summary}"}},
    ]
    if rca.root_cause:
        widgets.append({"textParagraph": {"text": f"<b>Nguyên nhân:</b> {rca.root_cause}"}})
    if rca.impact:
        widgets.append({"textParagraph": {"text": f"<b>Ảnh hưởng:</b> {rca.impact}"}})
    if rca.recommended_actions:
        actions = "<br>".join(f"{i}. {a}" for i, a in enumerate(rca.recommended_actions, 1))
        widgets.append({"textParagraph": {"text": f"<b>Hành động:</b><br>{actions}"}})
    if rca.check_commands:
        cmds = "<br>".join(rca.check_commands)
        widgets.append({"textParagraph": {"text": f"<b>Kiểm tra:</b><br>{cmds}"}})

    return {
        "cardsV2": [
            {
                "cardId": "hermes-rca",
                "card": {
                    "header": {
                        "title": f"{emoji} {alert.target_name}",
                        "subtitle": f"[{alert.severity.upper()}] {alert.alert_type} · model {rca.provider_used}",
                    },
                    "sections": [{"widgets": widgets}],
                },
            }
        ]
    }
