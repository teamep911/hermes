"""HMAC signing / verification round-trip."""
from hermes.security.hmac_auth import sign_body, verify_signature

SECRET = "test-secret"


def test_roundtrip():
    body = b'{"alert_type":"lock"}'
    sig = sign_body(SECRET, body)
    assert verify_signature(SECRET, body, sig)


def test_tampered_body_fails():
    body = b'{"alert_type":"lock"}'
    sig = sign_body(SECRET, body)
    assert not verify_signature(SECRET, b'{"alert_type":"block"}', sig)


def test_wrong_secret_fails():
    body = b"payload"
    sig = sign_body(SECRET, body)
    assert not verify_signature("other", body, sig)


def test_missing_header_fails():
    assert not verify_signature(SECRET, b"x", None)
