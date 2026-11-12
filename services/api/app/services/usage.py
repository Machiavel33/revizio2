"""Service de suivi d'usage, quotas et détection d'abus.

- Enregistre chaque appel IA (UsageRecord) avec coût estimé.
- Vérifie les quotas mensuels (audio minutes, nombre de fiches).
- Détecte les usages anormaux (rafale de cours, multi-IP = partage de compte).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Alert, Course, UsageRecord, User

# Tarifs indicatifs (USD) — à ajuster selon les grilles réelles
PRICING = {
    "openai": {"transcribe_per_min": 0.006, "sheet_in_per_1k": 0.0025, "sheet_out_per_1k": 0.01},
    "anthropic": {"sheet_in_per_1k": 0.003, "sheet_out_per_1k": 0.015},
    "deepgram": {"transcribe_per_min": 0.0043},
}


def estimate_cost(
    provider: str, kind: str, audio_seconds: float, in_tokens: int, out_tokens: int
) -> float:
    p = PRICING.get(provider, {})
    if kind == "transcribe":
        return round((audio_seconds / 60.0) * p.get("transcribe_per_min", 0.0), 6)
    return round(
        (in_tokens / 1000.0) * p.get("sheet_in_per_1k", 0.0)
        + (out_tokens / 1000.0) * p.get("sheet_out_per_1k", 0.0),
        6,
    )


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def record_usage(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID | None,
    kind: str,
    provider: str,
    key_source: str,
    audio_seconds: float = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    client_ip: str | None = None,
) -> UsageRecord:
    cost = estimate_cost(provider, kind, audio_seconds, input_tokens, output_tokens)
    rec = UsageRecord(
        user_id=user_id,
        course_id=course_id,
        kind=kind,
        provider=provider,
        key_source=key_source,
        audio_seconds=audio_seconds,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        client_ip=client_ip,
    )
    db.add(rec)
    await db.flush()
    return rec


async def monthly_usage(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Consommation du mois courant pour un utilisateur."""
    start = _month_start()
    audio = await db.scalar(
        select(func.coalesce(func.sum(UsageRecord.audio_seconds), 0)).where(
            UsageRecord.user_id == user_id, UsageRecord.created_at >= start
        )
    )
    sheets = await db.scalar(
        select(func.count())
        .select_from(UsageRecord)
        .where(
            UsageRecord.user_id == user_id,
            UsageRecord.kind == "sheet",
            UsageRecord.created_at >= start,
        )
    )
    cost = await db.scalar(
        select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
            UsageRecord.user_id == user_id, UsageRecord.created_at >= start
        )
    )
    return {
        "audio_minutes": round(float(audio or 0) / 60.0, 1),
        "sheet_count": int(sheets or 0),
        "cost_usd": round(float(cost or 0), 4),
    }


async def check_quota(db: AsyncSession, user_id: uuid.UUID, kind: str) -> tuple[bool, str]:
    """Vérifie si l'utilisateur peut effectuer l'action. Retourne (ok, raison)."""
    usage = await monthly_usage(db, user_id)
    if kind == "transcribe" and usage["audio_minutes"] >= settings.quota_audio_minutes:
        return False, f"Quota audio mensuel atteint ({settings.quota_audio_minutes} min)"
    if kind == "sheet" and usage["sheet_count"] >= settings.quota_sheet_count:
        return False, f"Quota de fiches mensuel atteint ({settings.quota_sheet_count})"
    return True, ""


async def maybe_alert_quota(db: AsyncSession, user: User) -> None:
    """Crée une alerte si l'utilisateur approche/dépasse son quota."""
    usage = await monthly_usage(db, user.id)
    ratio_audio = usage["audio_minutes"] / max(settings.quota_audio_minutes, 1)
    ratio_sheet = usage["sheet_count"] / max(settings.quota_sheet_count, 1)
    ratio = max(ratio_audio, ratio_sheet)
    if ratio >= settings.quota_alert_threshold:
        severity = "critical" if ratio >= 1.0 else "warning"
        # Évite les doublons : une alerte quota par user par jour
        since = datetime.now(UTC) - timedelta(hours=24)
        existing = await db.scalar(
            select(Alert.id).where(
                Alert.user_id == user.id,
                Alert.category == "quota",
                Alert.created_at >= since,
            )
        )
        if existing is None:
            db.add(
                Alert(
                    severity=severity,
                    category="quota",
                    title=f"Quota {int(ratio * 100)}% — {user.email}",
                    message=(
                        f"Audio: {usage['audio_minutes']}/{settings.quota_audio_minutes} min, "
                        f"Fiches: {usage['sheet_count']}/{settings.quota_sheet_count}"
                    ),
                    user_id=user.id,
                    metadata_={"usage": usage},
                )
            )
            await db.flush()


async def detect_abuse(db: AsyncSession, user: User, client_ip: str | None) -> list[str]:
    """Détecte des signaux d'abus. Retourne la liste des raisons détectées."""
    reasons = []
    now = datetime.now(UTC)

    # 1. Rafale de cours créés dans l'heure
    hour_ago = now - timedelta(hours=1)
    recent_courses = await db.scalar(
        select(func.count())
        .select_from(Course)
        .where(Course.user_id == user.id, Course.created_at >= hour_ago)
    )
    if int(recent_courses or 0) > settings.abuse_max_courses_per_hour:
        reasons.append(
            f"{recent_courses} cours créés en 1h (seuil {settings.abuse_max_courses_per_hour})"
        )

    # 2. Multi-IP : nombre d'IP distinctes sur 24h (partage de compte)
    day_ago = now - timedelta(hours=24)
    distinct_ips = await db.scalar(
        select(func.count(func.distinct(UsageRecord.client_ip))).where(
            UsageRecord.user_id == user.id,
            UsageRecord.created_at >= day_ago,
            UsageRecord.client_ip.is_not(None),
        )
    )
    if int(distinct_ips or 0) > settings.abuse_max_distinct_ips:
        reasons.append(
            f"{distinct_ips} IP distinctes en 24h "
            f"(seuil {settings.abuse_max_distinct_ips}) — partage de compte ?"
        )

    return reasons


async def raise_abuse_alert(db: AsyncSession, user: User, reasons: list[str]) -> None:
    if not reasons:
        return
    since = datetime.now(UTC) - timedelta(hours=6)
    existing = await db.scalar(
        select(Alert.id).where(
            Alert.user_id == user.id,
            Alert.category == "abuse",
            Alert.created_at >= since,
        )
    )
    if existing is None:
        db.add(
            Alert(
                severity="critical",
                category="abuse",
                title=f"Usage anormal — {user.email}",
                message="; ".join(reasons),
                user_id=user.id,
                metadata_={"reasons": reasons},
            )
        )
        await db.flush()
