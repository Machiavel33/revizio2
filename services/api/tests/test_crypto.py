"""Tests du chiffrement BYOK (AES-256-GCM)."""

import pytest

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_decrypt_roundtrip():
    secret = "sk-test-1234567890abcdef"
    blob = encrypt_secret(secret)
    assert isinstance(blob, bytes)
    assert blob != secret.encode()
    assert decrypt_secret(blob) == secret


def test_encrypt_is_randomized():
    secret = "sk-same-secret"
    assert encrypt_secret(secret) != encrypt_secret(secret)


def test_decrypt_invalid_blob_raises():
    with pytest.raises(ValueError):
        decrypt_secret(b"short")


def test_mask_secret():
    assert mask_secret("sk-1234567890abcd") == "sk-1...abcd"
    assert mask_secret("short") == "****"
