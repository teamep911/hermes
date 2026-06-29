"""HMAC-SHA256 authentication for the inbound OEM webhook.

The OEM-side `alert_push.sh` signs the raw request body with the shared
secret and sends it in the `X-Hermes-Signature` header as `sha256=<hex>`.
"""
from __future__ import annotations

import hashlib
import hmac


def sign_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_signature(secret: str, body: bytes, header_value: str | None) -> bool:
    if not secret or not header_value:
        return False
    expected = sign_body(secret, body)
    # constant-time comparison
    return hmac.compare_digest(expected, header_value.strip())
