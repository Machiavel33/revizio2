"""Tests de sécurité de l'upload audio (taille + type MIME)."""

import io

import pytest


async def _auth_headers(client, email="upload@example.com"):
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123"},
    )
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _create_course(client, headers):
    resp = await client.post("/api/courses", json={"title": "Cours"}, headers=headers)
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_upload_rejects_bad_content_type(client):
    headers = await _auth_headers(client)
    course_id = await _create_course(client, headers)
    files = {"file": ("evil.exe", io.BytesIO(b"MZ..."), "application/x-msdownload")}
    resp = await client.post(f"/api/courses/{course_id}/audio", files=files, headers=headers)
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(client):
    headers = await _auth_headers(client)
    course_id = await _create_course(client, headers)
    files = {"file": ("empty.wav", io.BytesIO(b""), "audio/wav")}
    resp = await client.post(f"/api/courses/{course_id}/audio", files=files, headers=headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(client, monkeypatch):
    from app.core.config import settings

    # Abaisse la limite pour le test
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    headers = await _auth_headers(client, "big@example.com")
    course_id = await _create_course(client, headers)
    big = io.BytesIO(b"x" * 2048)
    files = {"file": ("big.wav", big, "audio/wav")}
    resp = await client.post(f"/api/courses/{course_id}/audio", files=files, headers=headers)
    assert resp.status_code == 413
