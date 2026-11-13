"""Tests du service de factures (génération, numérotation, statut, PDF)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import UsageRecord, User
from app.services import invoices


@pytest.fixture
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=eng, expire_on_commit=False)
    async with factory() as session:
        yield session
    await eng.dispose()


async def _seed(db):
    u = User(email="fact@test.fr", display_name="Fact Test", password_hash="x")
    db.add(u)
    await db.flush()
    now = datetime.now(UTC)
    db.add(
        UsageRecord(
            user_id=u.id, kind="sheet", provider="openai", key_source="platform",
            input_tokens=1000, output_tokens=500, cost_usd=0.01, created_at=now,
        )
    )
    await db.flush()
    return u


async def test_generate_invoice(db):
    u = await _seed(db)
    now = datetime.now(UTC)
    inv = await invoices.generate_invoice(db, u.id, now.year, now.month)
    assert inv.number.startswith(f"FAC-{now.year:04d}{now.month:02d}-")
    assert inv.status == "draft"
    assert inv.total > 0
    assert len(inv.lines) == 1


async def test_generate_idempotent_draft(db):
    u = await _seed(db)
    now = datetime.now(UTC)
    inv1 = await invoices.generate_invoice(db, u.id, now.year, now.month)
    inv2 = await invoices.generate_invoice(db, u.id, now.year, now.month)
    assert inv1.id == inv2.id  # même brouillon réutilisé


async def test_issue_and_pay(db):
    u = await _seed(db)
    now = datetime.now(UTC)
    inv = await invoices.generate_invoice(db, u.id, now.year, now.month)
    inv = await invoices.issue_invoice(db, inv.id, due_days=30)
    assert inv.status == "sent"
    assert inv.issued_at is not None
    assert inv.due_at is not None
    inv = await invoices.mark_paid(db, inv.id)
    assert inv.status == "paid"
    assert inv.paid_at is not None


async def test_issue_twice_fails(db):
    u = await _seed(db)
    now = datetime.now(UTC)
    inv = await invoices.generate_invoice(db, u.id, now.year, now.month)
    await invoices.issue_invoice(db, inv.id)
    with pytest.raises(ValueError):
        await invoices.issue_invoice(db, inv.id)


async def test_invoice_pdf(db):
    u = await _seed(db)
    now = datetime.now(UTC)
    inv = await invoices.generate_invoice(db, u.id, now.year, now.month)
    await invoices.issue_invoice(db, inv.id)
    pdf = invoices.invoice_pdf(inv, u)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
