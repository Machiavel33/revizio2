"""Tests d'intégration : routes admin (RBAC + stats + users + jobs)."""

import pytest
from sqlalchemy import update

from app.models import User


async def _register(client, email: str) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    return resp.json()["access_token"]


async def _promote_to_admin(session_factory, email: str) -> None:
    async with session_factory() as db:
        await db.execute(update(User).where(User.email == email).values(role="admin"))
        await db.commit()


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client):
    token = await _register(client, "student@example.com")
    resp = await client.get("/api/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_and_users(client, session_factory):
    token = await _register(client, "admin@example.com")
    await _promote_to_admin(session_factory, "admin@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Crée un cours pour avoir des stats non nulles
    await client.post("/api/courses", json={"title": "Cours A"}, headers=headers)

    stats = await client.get("/api/admin/stats", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["total_users"] >= 1
    assert body["total_courses"] >= 1

    users = await client.get("/api/admin/users", headers=headers)
    assert users.status_code == 200
    assert any(u["email"] == "admin@example.com" for u in users.json())


@pytest.mark.asyncio
async def test_admin_toggle_user_active(client, session_factory):
    admin_token = await _register(client, "admin2@example.com")
    await _promote_to_admin(session_factory, "admin2@example.com")
    headers = {"Authorization": f"Bearer {admin_token}"}

    await _register(client, "target@example.com")
    users = await client.get("/api/admin/users", headers=headers)
    target = next(u for u in users.json() if u["email"] == "target@example.com")

    resp = await client.patch(
        f"/api/admin/users/{target['id']}",
        json={"is_active": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_jobs_list(client, session_factory):
    token = await _register(client, "admin3@example.com")
    await _promote_to_admin(session_factory, "admin3@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    jobs = await client.get("/api/admin/jobs", headers=headers)
    assert jobs.status_code == 200
    assert isinstance(jobs.json(), list)
