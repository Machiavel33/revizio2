"""Tests clés plateforme + mode de clé utilisateur (byok | platform)."""

import pytest
from sqlalchemy import update

from app.models import User


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


@pytest.mark.asyncio
async def test_platform_key_crud_admin_only(client, session_factory):
    # Non-admin refusé
    student = await _register(client, "s@example.com")
    denied = await client.get("/api/admin/platform-keys", headers=student)
    assert denied.status_code == 403

    # Admin OK
    admin = await _register(client, "a@example.com")
    await _promote(session_factory, "a@example.com")

    created = await client.post(
        "/api/admin/platform-keys",
        json={"provider": "openai", "api_key": "sk-platform-1234567890"},
        headers=admin,
    )
    assert created.status_code == 201
    key = created.json()
    assert key["provider"] == "openai"
    assert key["key_hint"] == "sk-p...7890"

    listed = await client.get("/api/admin/platform-keys", headers=admin)
    assert len(listed.json()) == 1

    # Doublon refusé
    dup = await client.post(
        "/api/admin/platform-keys",
        json={"provider": "openai", "api_key": "sk-other-1234567890"},
        headers=admin,
    )
    assert dup.status_code == 409

    deleted = await client.delete(f"/api/admin/platform-keys/{key['id']}", headers=admin)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_user_key_mode_switch(client, session_factory):
    admin = await _register(client, "admin@example.com")
    await _promote(session_factory, "admin@example.com")
    await client.post(
        "/api/admin/platform-keys",
        json={"provider": "openai", "api_key": "sk-platform-1234567890"},
        headers=admin,
    )

    user = await _register(client, "user@example.com")

    # Une clé plateforme existe -> défaut "platform" pour les nouveaux users
    status = await client.get("/api/api-keys/key-mode", headers=user)
    assert status.json()["key_mode"] == "platform"
    assert "openai" in status.json()["platform_available"]

    # Bascule vers byok
    switched = await client.put("/api/api-keys/key-mode", json={"key_mode": "byok"}, headers=user)
    assert switched.status_code == 200
    assert switched.json()["key_mode"] == "byok"

    # Mode invalide refusé
    bad = await client.put("/api/api-keys/key-mode", json={"key_mode": "xxx"}, headers=user)
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_platform_mode_requires_available_key(client):
    user = await _register(client, "nokey@example.com")
    # Aucune clé plateforme configurée -> bascule refusée
    resp = await client.put("/api/api-keys/key-mode", json={"key_mode": "platform"}, headers=user)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_users_show_key_info(client, session_factory):
    admin = await _register(client, "admin2@example.com")
    await _promote(session_factory, "admin2@example.com")
    await client.post(
        "/api/admin/platform-keys",
        json={"provider": "anthropic", "api_key": "sk-ant-platform-123456"},
        headers=admin,
    )

    # Un user avec une clé BYOK
    user = await _register(client, "byokuser@example.com")
    await client.post(
        "/api/api-keys",
        json={"provider": "openai", "api_key": "sk-user-1234567890"},
        headers=user,
    )

    users = await client.get("/api/admin/users", headers=admin)
    assert users.status_code == 200
    byok_user = next(u for u in users.json() if u["email"] == "byokuser@example.com")
    assert "openai" in byok_user["byok_providers"]
    assert "anthropic" in byok_user["platform_providers"]
    # Défaut platform (clé plateforme dispo), mais a une clé BYOK openai
    assert byok_user["key_mode"] == "platform"
