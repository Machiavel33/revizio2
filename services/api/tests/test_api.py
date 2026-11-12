"""Tests d'intégration : flux auth + BYOK + courses."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_login_me(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "password123", "display_name": "Alice"},
    )
    assert reg.status_code == 201
    tokens = reg.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    login = await client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "password123"},
    )
    assert login.status_code == 200

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "student@example.com"
    assert me.json()["role"] == "student"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "password123"},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_byok_create_list_delete(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "byok@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/api-keys",
        json={"provider": "openai", "api_key": "sk-test-abcdef123456", "is_default": True},
        headers=headers,
    )
    assert created.status_code == 201
    key = created.json()
    assert key["provider"] == "openai"
    assert key["key_hint"] == "sk-t...3456"

    listed = await client.get("/api/api-keys", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    deleted = await client.delete(f"/api/api-keys/{key['id']}", headers=headers)
    assert deleted.status_code == 204

    listed_after = await client.get("/api/api-keys", headers=headers)
    assert listed_after.json() == []


@pytest.mark.asyncio
async def test_course_crud(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "course@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    created = await client.post(
        "/api/courses",
        json={"title": "Droit constitutionnel", "subject": "Droit"},
        headers=headers,
    )
    assert created.status_code == 201
    course = created.json()
    assert course["title"] == "Droit constitutionnel"
    assert course["status"] == "recording"

    listed = await client.get("/api/courses", headers=headers)
    assert len(listed.json()) == 1

    detail = await client.get(f"/api/courses/{course['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["transcript"] is None

    updated = await client.patch(
        f"/api/courses/{course['id']}",
        json={"title": "Droit constitutionnel II"},
        headers=headers,
    )
    assert updated.json()["title"] == "Droit constitutionnel II"

    deleted = await client.delete(f"/api/courses/{course['id']}", headers=headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_course_isolation_between_users(client):
    a = await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "password123"},
    )
    b = await client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": "password123"},
    )
    headers_a = {"Authorization": f"Bearer {a.json()['access_token']}"}
    headers_b = {"Authorization": f"Bearer {b.json()['access_token']}"}

    course = await client.post("/api/courses", json={"title": "Secret"}, headers=headers_a)
    course_id = course.json()["id"]

    forbidden = await client.get(f"/api/courses/{course_id}", headers=headers_b)
    assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_byok_rotate(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "rotate@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    created = await client.post(
        "/api/api-keys",
        json={"provider": "openai", "api_key": "sk-old-key-1234567890", "is_default": True},
        headers=headers,
    )
    key_id = created.json()["id"]
    old_hint = created.json()["key_hint"]

    rotated = await client.post(
        f"/api/api-keys/{key_id}/rotate",
        json={"provider": "openai", "api_key": "sk-new-key-abcdefghij"},
        headers=headers,
    )
    assert rotated.status_code == 200
    assert rotated.json()["key_hint"] != old_hint
    assert rotated.json()["key_hint"] == "sk-n...ghij"


@pytest.mark.asyncio
async def test_byok_rotate_provider_mismatch(client):
    reg = await client.post(
        "/api/auth/register",
        json={"email": "rotatemis@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    created = await client.post(
        "/api/api-keys",
        json={"provider": "openai", "api_key": "sk-old-key-1234567890"},
        headers=headers,
    )
    key_id = created.json()["id"]
    resp = await client.post(
        f"/api/api-keys/{key_id}/rotate",
        json={"provider": "anthropic", "api_key": "sk-ant-new-1234567890"},
        headers=headers,
    )
    assert resp.status_code == 400
