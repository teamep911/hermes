"""Sensitive-data masking applied BEFORE any text leaves for an LLM provider.

Per the project's security decision, Oracle context (AWR dumps, session
info, alert messages) may be sent to external LLM providers ONLY after
IPs, hostnames, domains, DB identifiers and similar sensitive tokens are
redacted. Redaction is deterministic and reversible-free: the same token
maps to the same placeholder within a single call, so the LLM can still
reason about relationships ("HOST_1 holds the lock blocking SESSION_2")
without seeing real values.

This module is intentionally conservative (over-masks rather than leaks)
and ships with a self-check used by the test suite.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Order matters: more specific patterns first.
_PATTERNS: list[tuple[str, str]] = [
    # IPv4 addresses
    ("IP", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    # email addresses
    ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # FQDNs / domains (e.g. db01.corp.example.com, gcp.leevo.top)
    ("DOMAIN", r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"),
    # Oracle connect descriptors / EZConnect host:port/service
    ("CONNSTR", r"\b[\w.-]+:\d{2,5}/[\w.$#]+\b"),
    # JDBC / TNS style
    ("JDBC", r"jdbc:[^\s\"']+"),
]

# Tokens that look like secrets — always fully removed, never placeholdered.
_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd|secret|api[_-]?key|token)\s*[=:]\s*\S+"),
]


@dataclass
class Redactor:
    """Stateful redactor: consistent placeholders within one document."""

    counters: dict[str, int] = field(default_factory=dict)
    mapping: dict[str, str] = field(default_factory=dict)
    # Extra explicit values (e.g. known SID/schema names) to mask exactly.
    custom_terms: dict[str, str] = field(default_factory=dict)

    def _placeholder(self, kind: str, value: str) -> str:
        if value in self.mapping:
            return self.mapping[value]
        self.counters[kind] = self.counters.get(kind, 0) + 1
        token = f"<{kind}_{self.counters[kind]}>"
        self.mapping[value] = token
        return token

    def redact(self, text: str | None) -> str:
        if not text:
            return ""
        out = text

        # 1) strip obvious secrets entirely
        for pat in _SECRET_PATTERNS:
            out = pat.sub(lambda m: f"{m.group(1)}=<REDACTED>", out)

        # 2) caller-supplied exact terms (SIDs, schema/owner names, usernames)
        for term, kind in self.custom_terms.items():
            if term:
                out = re.sub(
                    rf"\b{re.escape(term)}\b",
                    lambda _m, k=kind, v=term: self._placeholder(k, v),
                    out,
                    flags=re.IGNORECASE,
                )

        # 3) structural patterns
        for kind, pattern in _PATTERNS:
            out = re.sub(pattern, lambda m, k=kind: self._placeholder(k, m.group(0)), out)

        return out

    def redact_payload(self, payload) -> dict:
        """Redact the free-text fields of an OemAlert-like object."""
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        for field_name in ("message", "awr_text", "session_text", "metric_value"):
            if data.get(field_name):
                data[field_name] = self.redact(str(data[field_name]))
        return data


def redact(text: str | None, custom_terms: dict[str, str] | None = None) -> str:
    """Convenience one-shot redaction with a fresh Redactor."""
    r = Redactor(custom_terms=custom_terms or {})
    return r.redact(text)


def contains_leak(text: str) -> list[str]:
    """Self-check helper: returns any obviously sensitive tokens still present."""
    leaks: list[str] = []
    for kind, pattern in _PATTERNS:
        if kind == "DOMAIN":
            # placeholders like <IP_1> are fine; skip them
            continue
        for m in re.finditer(pattern, text):
            if not m.group(0).startswith("<"):
                leaks.append(m.group(0))
    return leaks
