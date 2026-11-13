"""Tests du service de facturation (agrégation usage clé plateforme)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import UsageRecord, User
from app.services import billing


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
    u = User(email="etudiant@test.fr", display_name="Étudiant", password_hash="x")
    db.add(u)
    await db.flush()
    now = datetime.now(UTC)
    # 2 appels plateforme (facturables) + 1 BYOK (non facturable)
    db.add_all(
        [
            UsageRecord(
                user_id=u.id, kind="sheet", provider="openai", key_source="platform",
                input_tokens=1000, output_tokens=500, cost_usd=0.01, created_at=now,
            ),
            UsageRecord(
                user_id=u.id, kind="transcribe", provider="openai", key_source="platform",
                audio_seconds=120, cost_usd=0.012, created_at=now,
            ),
            UsageRecord(
                user_id=u.id, kind="sheet", provider="openai", key_source="byok",
                input_tokens=1000, output_tokens=500, cost_usd=0.01, created_at=now,
            ),
        ]
    )
    await db.flush()
    return u


async def test_billing_report_only_platform(db):
    await _seed(db)
    now = datetime.now(UTC)
    report = await billing.billing_report(db, now.year, now.month)
    assert len(report) == 1
    assert report[0]["email"] == "etudiant@test.fr"
    # Seuls les 2 appels plateforme comptent (0.01 + 0.012)
    assert report[0]["calls"] == 2
    assert abs(report[0]["cost_usd"] - 0.022) < 1e-6


async def test_user_billing_lines(db):
    u = await _seed(db)
    now = datetime.now(UTC)
    detail = await billing.user_billing(db, u.id, now.year, now.month)
    assert detail["period"] == f"{now.year:04d}-{now.month:02d}"
    kinds = {line["kind"] for line in detail["lines"]}
    assert kinds == {"sheet", "transcribe"}
    assert abs(detail["total_cost_usd"] - 0.022) < 1e-6


async def test_billing_csv(db):
    await _seed(db)
    now = datetime.now(UTC)
    csv_data = await billing.billing_csv(db, now.year, now.month)
    lines = csv_data.strip().splitlines()
    assert lines[0].startswith("user_id,email")
    assert "etudiant@test.fr" in lines[1]


async def test_billing_empty_month(db):
    report = await billing.billing_report(db, 2020, 1)
    assert report == []
