#!/usr/bin/env python3
"""Self-contained redactor for the OEM host (stdlib only, no deps).

Masks IPs, hostnames, domains, emails, connect strings and secrets BEFORE the
alert leaves the database host. Same value -> same placeholder within one run,
so the agent can still reason about relationships (<HOST_1> blocks <HOST_2>).

Usage:
    cat session.txt | redact.py
    redact.py "ORA-00060 from 10.1.2.3"
    redact.py --terms PAYROLL,FINANCE < dump.txt   # also mask these exact words
"""
import re
import sys

_PATTERNS = [
    ("IP", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    ("EMAIL", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ("DOMAIN", r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"),
    ("CONNSTR", r"\b[\w.-]+:\d{2,5}/[\w.$#]+\b"),
    ("JDBC", r"jdbc:[^\s\"']+"),
]
_SECRET = re.compile(r"(?i)(password|passwd|pwd|secret|api[_-]?key|token)\s*[=:]\s*\S+")


class Redactor:
    def __init__(self, terms=None):
        self.counters = {}
        self.mapping = {}
        self.terms = terms or []

    def _ph(self, kind, value):
        if value in self.mapping:
            return self.mapping[value]
        self.counters[kind] = self.counters.get(kind, 0) + 1
        token = "<%s_%d>" % (kind, self.counters[kind])
        self.mapping[value] = token
        return token

    def redact(self, text):
        if not text:
            return ""
        out = _SECRET.sub(lambda m: "%s=<REDACTED>" % m.group(1), text)
        for term in self.terms:
            if term:
                out = re.sub(
                    r"\b%s\b" % re.escape(term),
                    lambda _m, v=term: self._ph("TERM", v),
                    out,
                    flags=re.IGNORECASE,
                )
        for kind, pat in _PATTERNS:
            out = re.sub(pat, lambda m, k=kind: self._ph(k, m.group(0)), out)
        return out


def main(argv):
    terms = []
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == "--terms" and i + 1 < len(argv):
            terms = [t for t in argv[i + 1].split(",") if t]
            i += 2
        else:
            args.append(argv[i])
            i += 1
    text = " ".join(args) if args else sys.stdin.read()
    sys.stdout.write(Redactor(terms).redact(text))


if __name__ == "__main__":
    main(sys.argv[1:])
