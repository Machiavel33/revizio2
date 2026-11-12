"""Tests usage/quotas, alertes, mot de passe oublié."""

import pytest
from sqlalchemy import update

from app.models import User
from app.services import usage as usage_svc


async def _register(client, email):
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _promote(session_factory, email):
    async with session_factory() as db:
        await db.execute(update(User).where(User.email == email).values(role="admin"))
        await db.commit()


def test_estimate_cost():
    # Transcription : 10 min à 0.006/min = 0.06
    assert usage_svc.estimate_cost("openai", "transcribe", 600, 0, 0) == pytest.approx(0.06)
    # Fiche : 1000 in + 1000 out
    cost = usage_svc.estimate_cost("anthropic", "sheet", 0, 1000, 1000)
    assert cost == pytest.approx(0.003 + 0.015)


@pytest.mark.asyncio
async def test_usage_recorded_and_quota(client, session_factory):
    headers = await _register(client, "usage@example.com")
    me = await client.get("/api/auth/me", headers=headers)
    user_id = me.json()["id"]

    import uuid

    async with session_factory() as db:
        await usage_svc.record_usage(
            db,
            user_id=uuid.UUID(user_id),
            course_id=None,
            kind="transcribe",
            provider="openai",
            key_source="platform",
            audio_seconds=120,
        )
        await db.commit()
        usage = await usage_svc.monthly_usage(db, uuid.UUID(user_id))
        assert usage["audio_minutes"] == pytest.approx(2.0)
        assert usage["cost_usd"] > 0


@pytest.mark.asyncio
async def test_admin_usage_endpoint(client, session_factory):
    admin = await _register(client, "adminu@example.com")
    await _promote(session_factory, "adminu@example.com")
    resp = await client.get("/api/admin/usage", headers=admin)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_alerts_endpoints(client, session_factory):
    admin = await _register(client, "admina@example.com")
    await _promote(session_factory, "admina@example.com")

    alerts = await client.get("/api/admin/alerts", headers=admin)
    assert alerts.status_code == 200
    count = await client.get("/api/admin/alerts/count", headers=admin)
    assert count.status_code == 200
    assert "unread" in count.json()


@pytest.mark.asyncio
async def test_password_reset_flow(client, session_factory):
    await _register(client, "reset@example.com")

    # Demande de reset (réponse générique)
    forgot = await client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 202

    # Récupère le token en base (en prod il part par email)
    from sqlalchemy import select

    from app.models import PasswordResetToken

    async with session_factory() as db:
        tok = await db.scalar(select(PasswordResetToken))
        assert tok is not None
        # On ne peut pas récupérer le token en clair (hashé) — on teste le rejet d'un faux
    bad = await client.post(
        "/api/auth/reset-password",
        json={"token": "faux-token", "new_password": "newpassword123"},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_generic(client):
    # Anti-énumération : même réponse pour un email inconnu
    resp = await client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 202
