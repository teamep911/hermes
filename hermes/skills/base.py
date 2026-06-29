"""Skill base class — a single structured LLM call (prompt-chain, no agent loop).

Each skill builds a system + user prompt from the (already redacted) alert
plus recalled memory, asks the LLM for a strict JSON object, and parses it
into an RcaResult. Skills never see raw sensitive data — the pipeline
redacts before calling them.
"""
from __future__ import annotations

import abc
import json
import re

from ..llm import LLMError, get_router
from ..logging import get_logger
from ..models import RcaResult

log = get_logger("hermes.skills")

# Shared contract appended to every skill's system prompt.
JSON_CONTRACT = """
You MUST reply with a single valid JSON object and nothing else. Schema:
{
  "summary": string,                // 1-3 sentence Vietnamese summary
  "root_cause": string,             // most likely root cause
  "impact": string,                 // operational impact
  "recommended_actions": [string],  // ordered, concrete next steps
  "check_commands": [string],       // SQL / shell commands to confirm
  "confidence": "low" | "medium" | "high"
}
Placeholders like <IP_1>, <HOST_2>, <DOMAIN_1> are redacted real values;
reason about them as opaque identifiers and keep them verbatim in output.
"""


def _extract_json(text: str) -> dict:
    """Tolerant JSON extraction (strips code fences / surrounding prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


class Skill(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def system_prompt(self) -> str: ...

    @abc.abstractmethod
    def user_prompt(self, alert: dict, memory_block: str) -> str: ...

    async def run(self, alert: dict, memory_block: str = "") -> RcaResult:
        router = get_router()
        result = await router.complete(
            system=self.system_prompt() + "\n" + JSON_CONTRACT,
            user=self.user_prompt(alert, memory_block),
        )
        try:
            data = _extract_json(result.text)
        except json.JSONDecodeError:
            log.warning("skill_json_parse_failed", skill=self.name)
            data = {"summary": result.text.strip()[:2000], "confidence": "low"}

        return RcaResult(
            skill=self.name,
            summary=data.get("summary", ""),
            root_cause=data.get("root_cause", ""),
            impact=data.get("impact", ""),
            recommended_actions=list(data.get("recommended_actions", []) or []),
            check_commands=list(data.get("check_commands", []) or []),
            confidence=data.get("confidence", "medium"),
            provider_used=result.provider,
            model_used=result.model,
        )


_REGISTRY: dict[str, type[Skill]] = {}


def register(cls: type[Skill]) -> type[Skill]:
    _REGISTRY[cls.name] = cls
    return cls


def get_skill(name: str) -> Skill:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown skill: {name}")
    return cls()
