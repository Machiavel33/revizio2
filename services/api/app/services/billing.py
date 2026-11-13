"""Service de facturation : refacturation de l'usage de la clé plateforme.

Modèle de prix **équitable et prévisible** : l'étudiant paie des prix publics
simples (par heure d'audio, par fiche, par quiz) plutôt qu'un coût brut × marge
opaque. L'établissement couvre ses coûts fournisseur + une marge raisonnable.

    montant_ligne = quantité × prix_public
    sous_total    = Σ montants_lignes
    total         = max(sous_total, plancher_mensuel) × (1 + TVA)

Un garde-fou (`billing_markup`) permet de vérifier que les prix publics couvrent
le coût réel : si `coût_réel × markup > prix_public`, on signale une marge négative
dans le rapport (l'admin peut alors ajuster les prix).
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


def _public_price(kind: str, audio_seconds: float, calls: int) -> float:
    """Prix public d'une ligne selon le type d'usage (devise d'affichage)."""
    if kind == "transcribe":
        return round((audio_seconds / 3600.0) * settings.billing_price_per_audio_hour, 4)
    if kind == "sheet":
        return round(calls * settings.billing_price_per_sheet, 4)
    if kind == "quiz":
        return round(calls * settings.billing_price_per_quiz, 4)
    return 0.0


def _apply_floor_and_vat(subtotal: float) -> tuple[float, float, float]:
    """Applique le plancher mensuel et la TVA. Retourne (base, tva, total)."""
    base = max(subtotal, settings.billing_min_monthly)
    vat = round(base * settings.billing_vat_rate, 4)
    total = round(base + vat, 4)
    return round(base, 4), vat, total


async def user_billing(db: AsyncSession, user_id: uuid.UUID, year: int, month: int) -> dict:
    """Détail de facturation d'un utilisateur pour un mois (clé plateforme)."""
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
    subtotal = 0.0
    real_cost = 0.0
    for provider, kind, calls, audio_s, in_tok, out_tok, cost in rows:
        calls = int(calls)
        audio_s = float(audio_s or 0)
        cost = float(cost or 0)
        price = _public_price(kind, audio_s, calls)
        subtotal += price
        real_cost += cost
        lines.append(
            {
                "provider": provider,
                "kind": kind,
                "calls": calls,
                "audio_minutes": round(audio_s / 60.0, 1),
                "input_tokens": int(in_tok or 0),
                "output_tokens": int(out_tok or 0),
                "unit_price": _unit_price(kind),
                "amount": price,
                "cost_usd": round(cost, 4),
            }
        )

    base, vat, total = _apply_floor_and_vat(subtotal)
    # Garde-fou : le prix public couvre-t-il le coût réel (avec marge) ?
    covered = (real_cost * settings.billing_markup * settings.billing_usd_rate) <= base
    return {
        "user_id": str(user_id),
        "period": f"{year:04d}-{month:02d}",
        "lines": lines,
        "subtotal": round(subtotal, 4),
        "base": base,
        "vat": vat,
        "total": total,
        "currency": settings.billing_currency,
        "real_cost_usd": round(real_cost, 4),
        "margin_covered": covered,
    }


def _unit_price(kind: str) -> float:
    if kind == "transcribe":
        return settings.billing_price_per_audio_hour
    if kind == "sheet":
        return settings.billing_price_per_sheet
    if kind == "quiz":
        return settings.billing_price_per_quiz
    return 0.0


async def billing_report(db: AsyncSession, year: int, month: int) -> list[dict]:
    """Rapport de facturation de tous les utilisateurs (clé plateforme)."""
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
        detail = await user_billing(db, uid, year, month)
        report.append(
            {
                "user_id": str(uid),
                "email": email,
                "display_name": name,
                "calls": int(calls),
                "cost_usd": round(float(cost or 0), 4),
                "subtotal": detail["subtotal"],
                "total": detail["total"],
                "currency": settings.billing_currency,
                "margin_covered": detail["margin_covered"],
            }
        )
    return report


async def billing_csv(db: AsyncSession, year: int, month: int) -> str:
    """Export CSV du rapport de facturation (une ligne par utilisateur)."""
    report = await billing_report(db, year, month)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "user_id",
            "email",
            "display_name",
            "calls",
            "cost_usd",
            "subtotal",
            "total",
            "currency",
            "period",
        ]
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
                r["subtotal"],
                r["total"],
                r["currency"],
                period,
            ]
        )
    return buf.getvalue()
