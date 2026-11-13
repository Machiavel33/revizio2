"""Service de facturation : refacturation de l'usage de la clé plateforme.

Quand un étudiant est en mode `platform` (il utilise la clé API de l'établissement),
c'est l'établissement qui paie le fournisseur. Ce service agrège la consommation
réelle (`usage_records` où `key_source='platform'`) par utilisateur et par mois,
applique une marge configurable, et produit un rapport facturable + un export CSV.

Les coûts sont stockés en USD (coût réel fournisseur). L'affichage applique :
    montant_facturé = coût_usd × marge × taux_usd_vers_devise
"""

import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import UsageRecord, User


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + (month == 12), (month % 12) + 1, 1, tzinfo=UTC)
    return start, end


def _billable(cost_usd: float) -> float:
    """Montant refacturé (marge + conversion devise)."""
    return round(cost_usd * settings.billing_markup * settings.billing_usd_rate, 4)


async def user_billing(
    db: AsyncSession, user_id: uuid.UUID, year: int, month: int
) -> dict:
    """Détail de facturation d'un utilisateur pour un mois donné (clé plateforme)."""
    start, end = _month_bounds(year, month)
    rows = (
        await db.execute(
            select(
                UsageRecord.provider,
                UsageRecord.kind,
                func.count().label("calls"),
                func.coalesce(func.sum(UsageRecord.audio_seconds), 0).label("audio_s"),
                func.coalesce(func.sum(UsageRecord.input_tokens), 0).label("in_tok"),
                func.coalesce(func.sum(UsageRecord.output_tokens), 0).label("out_tok"),
                func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("cost"),
            )
            .where(
                UsageRecord.user_id == user_id,
                UsageRecord.key_source == "platform",
                UsageRecord.created_at >= start,
                UsageRecord.created_at < end,
            )
            .group_by(UsageRecord.provider, UsageRecord.kind)
        )
    ).all()

    lines = []
    total_cost = 0.0
    for provider, kind, calls, audio_s, in_tok, out_tok, cost in rows:
        cost = float(cost or 0)
        total_cost += cost
        lines.append(
            {
                "provider": provider,
                "kind": kind,
                "calls": int(calls),
                "audio_minutes": round(float(audio_s or 0) / 60.0, 1),
                "input_tokens": int(in_tok or 0),
                "output_tokens": int(out_tok or 0),
                "cost_usd": round(cost, 4),
                "billed": _billable(cost),
            }
        )

    return {
        "user_id": str(user_id),
        "period": f"{year:04d}-{month:02d}",
        "lines": lines,
        "total_cost_usd": round(total_cost, 4),
        "total_billed": _billable(total_cost),
        "currency": settings.billing_currency,
        "markup": settings.billing_markup,
    }


async def billing_report(db: AsyncSession, year: int, month: int) -> list[dict]:
    """Rapport de facturation de tous les utilisateurs ayant consommé la clé plateforme."""
    start, end = _month_bounds(year, month)
    rows = (
        await db.execute(
            select(
                User.id,
                User.email,
                User.display_name,
                func.coalesce(func.sum(UsageRecord.cost_usd), 0).label("cost"),
                func.count().label("calls"),
            )
            .join(UsageRecord, UsageRecord.user_id == User.id)
            .where(
                UsageRecord.key_source == "platform",
                UsageRecord.created_at >= start,
                UsageRecord.created_at < end,
            )
            .group_by(User.id, User.email, User.display_name)
            .order_by(func.sum(UsageRecord.cost_usd).desc())
        )
    ).all()

    report = []
    for uid, email, name, cost, calls in rows:
        cost = float(cost or 0)
        report.append(
            {
                "user_id": str(uid),
                "email": email,
                "display_name": name,
                "calls": int(calls),
                "cost_usd": round(cost, 4),
                "billed": _billable(cost),
                "currency": settings.billing_currency,
            }
        )
    return report


async def billing_csv(db: AsyncSession, year: int, month: int) -> str:
    """Export CSV du rapport de facturation (une ligne par utilisateur)."""
    report = await billing_report(db, year, month)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["user_id", "email", "display_name", "calls", "cost_usd", "billed", "currency", "period"]
    )
    period = f"{year:04d}-{month:02d}"
    for r in report:
        writer.writerow(
            [
                r["user_id"],
                r["email"],
                r["display_name"],
                r["calls"],
                r["cost_usd"],
                r["billed"],
                r["currency"],
                period,
            ]
        )
    return buf.getvalue()
