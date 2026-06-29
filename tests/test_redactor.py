"""Redactor must mask IPs/hosts/domains/secrets before LLM calls."""
from hermes.security.redactor import Redactor, contains_leak, redact


def test_ip_is_masked():
    out = redact("connection from 10.20.30.40 failed")
    assert "10.20.30.40" not in out
    assert "<IP_1>" in out


def test_same_value_same_placeholder():
    r = Redactor()
    out = r.redact("host 10.0.0.1 talks to 10.0.0.1 and 10.0.0.2")
    assert out.count("<IP_1>") == 2
    assert "<IP_2>" in out


def test_domain_and_email_masked():
    out = redact("alert from db01.corp.example.com sent to ops@example.com")
    assert "example.com" not in out
    assert "<DOMAIN_1>" in out and "<EMAIL_1>" in out


def test_secret_stripped():
    out = redact("password=SuperSecret123 in tnsnames")
    assert "SuperSecret123" not in out
    assert "REDACTED" in out


def test_custom_terms_masked():
    out = redact("ORA-00060 on schema PAYROLL owner FINANCE",
                 custom_terms={"PAYROLL": "SCHEMA", "FINANCE": "OWNER"})
    assert "PAYROLL" not in out and "FINANCE" not in out


def test_no_leak_after_redaction():
    sample = (
        "Session from 192.168.1.50 (host prod-db.internal.example.org) "
        "blocked; contact dba@example.org; api_key=abc123xyz"
    )
    out = redact(sample)
    assert contains_leak(out) == []
