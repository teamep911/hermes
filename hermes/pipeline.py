"""End-to-end alert processing pipeline (linear prompt-chain).

Steps:
  1. select skill from alert type
  2. redact sensitive data (IPs/hosts/domains/secrets) -> safe to send to LLM
  3. dedup + severity gate (cost/latency control)
  4. recall similar past incidents (pgvector)
  5. run the skill (single LLM call via provider router)
  6. persist incident + embedding (redacted form only)
  7. format -> push card to Google Chat
"""
from __future__ import annotations

from .chat import get_chat_client
from .config import get_settings
from .formatter import to_google_chat_card, to_markdown
from .logging import get_logger
from .memory import is_duplicate, persist_incident, recall_similar, render_memory_block
from .models import OemAlert, RcaResult, WebhookResponse
from .security.redactor import Redactor
from .skills import get_skill

log = get_logger("hermes.pipeline")


def select_skill(alert: OemAlert) -> str:
    t = alert.alert_type.lower()
    if t in {"lock", "block", "session"}:
        return "rca_oracle"
    if alert.awr_text or "awr" in t or (alert.metric_name or "").lower() in {
        "cpu",
        "io",
        "memory",
    }:
        return "awr_summary"
    return "analyze_alert"


def _redact_alert(alert: OemAlert) -> dict:
    """Mask sensitive fields. Known identifiers from the payload are masked
    exactly so they stay consistent across free-text fields."""
    custom = {}
    if alert.target_name:
        custom[alert.target_name] = "TARGET"
    for term in alert.extra.get("mask_terms", []):
        custom[term] = "TERM"
    redactor = Redactor(custom_terms=custom)
    return redactor.redact_payload(alert)


def _recall_text(redacted: dict) -> str:
    return " ".join(
        str(redacted.get(k, ""))
        for k in ("alert_type", "metric_name", "message", "session_text")
    ).strip()


async def process_alert(alert: OemAlert) -> WebhookResponse:
    s = get_settings()
    signature = alert.error_signature()

    # cost gate 1: severity
    if not s.severity_meets_threshold(alert.severity):
        log.info("skip_below_severity", signature=signature, severity=alert.severity)
        return WebhookResponse(status="skipped", skipped_reason="below_severity_threshold")

    # cost gate 2: dedup
    try:
        if await is_duplicate(signature, s.dedup_window_seconds):
            log.info("skip_duplicate", signature=signature)
            return WebhookResponse(status="skipped", skipped_reason="duplicate_within_window")
    except Exception as exc:  # DB not ready shouldn't drop the alert
        log.warning("dedup_check_failed", error=str(exc))

    # redact BEFORE anything leaves the process
    redacted = _redact_alert(alert)
    recall_text = _recall_text(redacted)

    # recall similar incidents
    similar: list[dict] = []
    try:
        similar = await recall_similar(recall_text, s.memory_top_k, s.memory_min_score)
    except Exception as exc:
        log.warning("recall_failed", error=str(exc))

    memory_block = render_memory_block(similar)

    # run the skill (single LLM call, redacted input only)
    skill_name = select_skill(alert)
    skill = get_skill(skill_name)
    rca: RcaResult = await skill.run(redacted, memory_block)
    rca.similar_incidents = [r["id"] for r in similar]

    # persist (redacted form only)
    try:
        rca.incident_id = await persist_incident(signature, redacted, rca, recall_text)
    except Exception as exc:
        log.warning("persist_failed", error=str(exc))

    # deliver to Google Chat
    try:
        await get_chat_client().send_card(to_google_chat_card(alert, rca))
    except Exception as exc:
        log.warning("chat_delivery_failed", error=str(exc))

    log.info(
        "alert_processed",
        signature=signature,
        skill=skill_name,
        provider=rca.provider_used,
        incident_id=rca.incident_id,
    )
    # markdown kept for API consumers / debugging
    rca_markdown = to_markdown(alert, rca)
    log.debug("rca_markdown", text=rca_markdown)
    return WebhookResponse(status="processed", incident_id=rca.incident_id)
