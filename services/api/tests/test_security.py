"""Tests de sécurité : hash de mot de passe et JWT."""

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("super-secret-password")
    assert hashed != "super-secret-password"
    assert verify_password("super-secret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-123")
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_refresh_token_type_mismatch():
    token = create_refresh_token("user-123")
    with pytest.raises(TokenError):
        decode_token(token, expected_type="access")


def test_invalid_token_raises():
    with pytest.raises(TokenError):
        decode_token("not-a-valid-token")
