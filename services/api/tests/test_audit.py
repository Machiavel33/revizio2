"""Tests du journal d'audit immuable (chaîne de hachage)."""

import pytest
from sqlalchemy import select, update

from app.models import AuditLog
from app.services import audit


@pytest.mark.asyncio
async def test_audit_chain_integrity(client, session_factory):
    # Génère des entrées via des actions réelles
    await client.post(
        "/api/auth/register",
        json={"email": "audit@example.com", "password": "password123"},
    )
    await client.post(
        "/api/auth/login",
        json={"email": "audit@example.com", "password": "password123"},
    )

    async with session_factory() as db:
        ok, broken = await audit.verify_chain(db)
        assert ok is True
        assert broken is None
        entries = (await db.scalars(select(AuditLog).order_by(AuditLog.seq))).all()
        assert len(entries) >= 2
        # Chaîne correctement liée
        for i in range(1, len(entries)):
            assert entries[i].prev_hash == entries[i - 1].entry_hash


@pytest.mark.asyncio
async def test_audit_detects_tampering(client, session_factory):
    await client.post(
        "/api/auth/register",
        json={"email": "tamper@example.com", "password": "password123"},
    )

    async with session_factory() as db:
        ok, _ = await audit.verify_chain(db)
        assert ok is True

        # Altère une entrée (simule une falsification en base)
        first = await db.scalar(select(AuditLog).order_by(AuditLog.seq).limit(1))
        await db.execute(
            update(AuditLog).where(AuditLog.id == first.id).values(action="tampered.action")
        )
        await db.commit()

    async with session_factory() as db:
        ok, broken = await audit.verify_chain(db)
        assert ok is False
        assert broken == first.seq


@pytest.mark.asyncio
async def test_audit_admin_endpoints(client, session_factory):
    from sqlalchemy import update as sql_update

    from app.models import User

    reg = await client.post(
        "/api/auth/register",
        json={"email": "auditadmin@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    async with session_factory() as db:
        await db.execute(
            sql_update(User).where(User.email == "auditadmin@example.com").values(role="admin")
        )
        await db.commit()
    headers = {"Authorization": f"Bearer {token}"}

    listing = await client.get("/api/admin/audit", headers=headers)
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)

    verify = await client.get("/api/admin/audit/verify", headers=headers)
    assert verify.status_code == 200
    body = verify.json()
    assert body["ok"] is True
    assert body["total_entries"] >= 1
