"""Tests 2FA TOTP : enroll, login challenge, verify, backup codes, disable."""

import pyotp
import pytest


async def _register(client, email="mfa@example.com"):
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


@pytest.mark.asyncio
async def test_2fa_full_flow(client):
    headers = await _register(client)

    # 1. Setup : récupère le secret
    setup = await client.post("/api/2fa/setup", headers=headers)
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["provisioning_uri"].startswith("otpauth://totp/")

    # 2. Enable avec un code valide
    code = pyotp.TOTP(secret).now()
    enable = await client.post("/api/2fa/enable", json={"code": code}, headers=headers)
    assert enable.status_code == 200
    backup_codes = enable.json()["backup_codes"]
    assert len(backup_codes) == 8

    # 3. Status
    status = await client.get("/api/2fa/status", headers=headers)
    assert status.json()["enabled"] is True

    # 4. Login → challenge MFA (pas de tokens)
    login = await client.post(
        "/api/auth/login",
        json={"email": "mfa@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body.get("mfa_required") is True
    assert "mfa_token" in body
    assert "access_token" not in body

    # 5. Verify avec code TOTP → tokens finaux
    code2 = pyotp.TOTP(secret).now()
    verify = await client.post(
        "/api/2fa/verify",
        json={"mfa_token": body["mfa_token"], "code": code2},
    )
    assert verify.status_code == 200
    assert "access_token" in verify.json()


@pytest.mark.asyncio
async def test_2fa_verify_with_backup_code(client):
    headers = await _register(client, "mfa2@example.com")
    setup = await client.post("/api/2fa/setup", headers=headers)
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    enable = await client.post("/api/2fa/enable", json={"code": code}, headers=headers)
    backup = enable.json()["backup_codes"][0]

    login = await client.post(
        "/api/auth/login",
        json={"email": "mfa2@example.com", "password": "password123"},
    )
    mfa_token = login.json()["mfa_token"]

    # Backup code fonctionne
    verify = await client.post(
        "/api/2fa/verify",
        json={"mfa_token": mfa_token, "code": backup},
    )
    assert verify.status_code == 200

    # Le backup code est consommé : un 2e usage échoue
    login2 = await client.post(
        "/api/auth/login",
        json={"email": "mfa2@example.com", "password": "password123"},
    )
    verify2 = await client.post(
        "/api/2fa/verify",
        json={"mfa_token": login2.json()["mfa_token"], "code": backup},
    )
    assert verify2.status_code == 401


@pytest.mark.asyncio
async def test_2fa_enable_wrong_code(client):
    headers = await _register(client, "mfa3@example.com")
    await client.post("/api/2fa/setup", headers=headers)
    resp = await client.post("/api/2fa/enable", json={"code": "000000"}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_2fa_disable(client):
    headers = await _register(client, "mfa4@example.com")
    setup = await client.post("/api/2fa/setup", headers=headers)
    secret = setup.json()["secret"]
    code = pyotp.TOTP(secret).now()
    await client.post("/api/2fa/enable", json={"code": code}, headers=headers)

    disable = await client.post(
        "/api/2fa/disable",
        json={"code": pyotp.TOTP(secret).now()},
        headers=headers,
    )
    assert disable.status_code == 200
    assert disable.json()["enabled"] is False

    # Login sans challenge après désactivation
    login = await client.post(
        "/api/auth/login",
        json={"email": "mfa4@example.com", "password": "password123"},
    )
    assert "access_token" in login.json()
