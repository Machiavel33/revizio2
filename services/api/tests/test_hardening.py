"""Tests du hardening : headers de sécurité et rate-limiting."""

import pytest


@pytest.mark.asyncio
async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_rate_limit_auth(client):
    # La limite auth est de 20/min : on dépasse volontairement.
    last_status = None
    for i in range(25):
        resp = await client.post(
            "/api/auth/login",
            json={"email": f"nobody{i}@example.com", "password": "wrongpass"},
        )
        last_status = resp.status_code
    assert last_status == 429
