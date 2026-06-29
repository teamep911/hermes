"""Pydantic schemas for the OEM -> Hermes payload and internal results."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["info", "warning", "critical", "fatal"]


class OemAlert(BaseModel):
    """Full payload pushed by the OEM-side collectors (alert_push.sh)."""

    # core alert
    alert_type: str = Field(..., description="threshold | lock | block | session | custom")
    target_name: str
    target_type: str = "oracle_database"
    metric_name: Optional[str] = None
    metric_value: Optional[str] = None
    severity: Severity = "warning"
    message: str = ""
    event_time: Optional[str] = None

    # enriched context gathered on the OEM host
    awr_text: Optional[str] = Field(None, description="Output of awr_export.sh")
    session_text: Optional[str] = Field(None, description="Output of check_session.sh")
    extra: dict[str, Any] = Field(default_factory=dict)

    def error_signature(self) -> str:
        """Stable key used for dedup and similar-error recall."""
        return f"{self.alert_type}|{self.target_name}|{self.metric_name or ''}|{self.severity}"


class RcaResult(BaseModel):
    incident_id: Optional[int] = None
    skill: str
    summary: str
    root_cause: str = ""
    impact: str = ""
    recommended_actions: list[str] = Field(default_factory=list)
    check_commands: list[str] = Field(default_factory=list)
    provider_used: str = ""
    model_used: str = ""
    similar_incidents: list[int] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


class WebhookResponse(BaseModel):
    status: str
    incident_id: Optional[int] = None
    skipped_reason: Optional[str] = None
