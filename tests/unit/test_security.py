"""
Unit tests for cryptographic security utilities (HMAC-SHA256 & SHA-256).
"""

import hashlib
import hmac
from app.core.security import verify_razorpay_signature, sha256_hex


def test_verify_razorpay_signature_valid():
    secret = "secret_webhook_key_123"
    payload = b'{"event":"subscription.activated","id":"sub_001"}'
    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert verify_razorpay_signature(payload, valid_sig, secret) is True


def test_verify_razorpay_signature_tampered_payload():
    secret = "secret_webhook_key_123"
    original = b'{"event":"subscription.activated","id":"sub_001"}'
    tampered = b'{"event":"subscription.activated","id":"sub_002"}'
    valid_sig = hmac.new(secret.encode("utf-8"), original, hashlib.sha256).hexdigest()

    assert verify_razorpay_signature(tampered, valid_sig, secret) is False


def test_verify_razorpay_signature_invalid_secret():
    payload = b'{"event":"subscription.activated"}'
    valid_sig = hmac.new(b"secret_a", payload, hashlib.sha256).hexdigest()

    assert verify_razorpay_signature(payload, valid_sig, "wrong_secret") is False


def test_sha256_hex():
    data = "test_data_string"
    expected = hashlib.sha256(b"test_data_string").hexdigest()
    assert sha256_hex(data) == expected
