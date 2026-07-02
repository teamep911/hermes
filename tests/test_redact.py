"""Tests for the OEM-side masking script (scripts/redact.py)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "oem-host", "scripts"))

from redact import Redactor  # noqa: E402


def test_ip_masked():
    out = Redactor().redact("connection from 10.20.30.40 failed")
    assert "10.20.30.40" not in out and "<IP_1>" in out


def test_stable_placeholder():
    out = Redactor().redact("10.0.0.1 talks to 10.0.0.1 and 10.0.0.2")
    assert out.count("<IP_1>") == 2 and "<IP_2>" in out


def test_domain_and_email():
    out = Redactor().redact("from db01.corp.example.com to ops@example.com")
    assert "example.com" not in out and "<DOMAIN_1>" in out and "<EMAIL_1>" in out


def test_secret_stripped():
    out = Redactor().redact("password=SuperSecret123")
    assert "SuperSecret123" not in out and "REDACTED" in out


def test_custom_terms():
    out = Redactor(["PAYROLL", "FINANCE"]).redact("ORA-00060 schema PAYROLL owner FINANCE")
    assert "PAYROLL" not in out and "FINANCE" not in out


def test_no_leak():
    sample = (
        "Session from 192.168.1.50 (host prod-db.internal.example.org) blocked; "
        "contact dba@example.org; api_key=abc123xyz"
    )
    out = Redactor().redact(sample)
    import re
    # no bare IPv4 should survive
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out)
    assert "abc123xyz" not in out and "example.org" not in out
