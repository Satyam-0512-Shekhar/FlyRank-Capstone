"""
FlyRank Capstone — Webhook signature security utilities.

Uses HMAC-SHA256 with constant-time comparison to prevent timing attacks.
Raw bytes must be preserved and passed directly — no JSON re-encoding.
"""

import hashlib
import hmac


def verify_razorpay_signature(
    raw_body: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    """
    Verify a Razorpay webhook signature.

    Razorpay computes: HMAC-SHA256(raw_body, webhook_secret)
    and sends the hex digest in X-Razorpay-Signature header.

    Returns True if valid, False otherwise.
    Uses hmac.compare_digest() for constant-time comparison
    to prevent timing-oracle attacks.
    """
    expected = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def sha256_hex(data: str) -> str:
    """Return SHA-256 hex digest of a UTF-8 string. Used for request_hash."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()
