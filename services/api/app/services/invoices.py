"""Service de factures : génération depuis l'usage, numérotation, statut, PDF.

Une facture fige un snapshot des lignes au moment de l'émission (les prix publics
peuvent changer sans réécrire l'historique). Numérotation séquentielle par période :
FAC-YYYYMM-NNNN.
"""

import io
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Invoice, User
from app.services import billing as billing_svc


async def _next_number(db: AsyncSession, period: str) -> str:
    """Numéro séquentiel pour la période : FAC-YYYYMM-NNNN."""
    count = await db.scalar(
        select(func.count()).select_from(Invoice).where(Invoice.period == period)
    )
    seq = int(count or 0) + 1
    return f"FAC-{period.replace('-', '')}-{seq:04d}"


async def generate_invoice(
    db: AsyncSession, user_id: uuid.UUID, year: int, month: int
) -> Invoice:
    """Génère (ou régénère en brouillon) la facture d'un utilisateur pour un mois."""
    period = f"{year:04d}-{month:02d}"
    detail = await billing_svc.user_billing(db, user_id, year, month)

    # Réutilise un brouillon existant pour la même période (idempotent).
    existing = await db.scalar(
        select(Invoice).where(
            Invoice.user_id == user_id,
            Invoice.period == period,
            Invoice.status == "draft",
        )
    )
    number = existing.number if existing else await _next_number(db, period)

    inv = existing or Invoice(number=number, user_id=user_id, period=period)
    inv.currency = detail["currency"]
    inv.subtotal = detail["subtotal"]
    inv.vat = detail["vat"]
    inv.total = detail["total"]
    inv.lines = detail["lines"]
    if existing is None:
        db.add(inv)
    await db.flush()
    return inv


async def issue_invoice(db: AsyncSession, invoice_id: uuid.UUID, due_days: int = 30) -> Invoice:
    """Émet une facture (draft -> sent) avec une échéance."""
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise ValueError("Facture introuvable")
    if inv.status != "draft":
        raise ValueError(f"Facture déjà {inv.status}")
    now = datetime.now(UTC)
    inv.status = "sent"
    inv.issued_at = now
    inv.due_at = now + timedelta(days=due_days)
    await db.flush()
    return inv


async def mark_paid(
    db: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    stripe_session_id: str | None = None,
    stripe_payment_intent: str | None = None,
) -> Invoice:
    """Marque une facture comme payée."""
    inv = await db.get(Invoice, invoice_id)
    if inv is None:
        raise ValueError("Facture introuvable")
    inv.status = "paid"
    inv.paid_at = datetime.now(UTC)
    if stripe_session_id:
        inv.stripe_session_id = stripe_session_id
    if stripe_payment_intent:
        inv.stripe_payment_intent = stripe_payment_intent
    await db.flush()
    return inv


async def refresh_overdue(db: AsyncSession) -> int:
    """Passe en 'overdue' les factures 'sent' dont l'échéance est dépassée."""
    now = datetime.now(UTC)
    rows = await db.scalars(
        select(Invoice).where(
            Invoice.status == "sent",
            Invoice.due_at.is_not(None),
            Invoice.due_at < now,
        )
    )
    n = 0
    for inv in rows:
        inv.status = "overdue"
        n += 1
    if n:
        await db.flush()
    return n


def invoice_pdf(invoice: Invoice, user: User) -> bytes:
    """Génère la facture en PDF (reportlab). Retourne les octets."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{settings.billing_issuer_name}</b>", styles["Title"]))
    if settings.billing_issuer_address:
        story.append(Paragraph(settings.billing_issuer_address, styles["Normal"]))
    if settings.billing_issuer_vat:
        story.append(Paragraph(f"TVA : {settings.billing_issuer_vat}", styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(f"<b>Facture {invoice.number}</b>", styles["Heading2"]))
    story.append(Paragraph(f"Période : {invoice.period}", styles["Normal"]))
    story.append(Paragraph(f"Émise le : {_fmt(invoice.issued_at)}", styles["Normal"]))
    if invoice.due_at:
        story.append(Paragraph(f"Échéance : {_fmt(invoice.due_at)}", styles["Normal"]))
    story.append(Paragraph(f"Statut : {invoice.status}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("<b>Client</b>", styles["Heading3"]))
    story.append(Paragraph(user.display_name or user.email, styles["Normal"]))
    story.append(Paragraph(user.email, styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    # Tableau des lignes
    data = [["Type", "Quantité", "Prix unitaire", "Montant"]]
    for line in invoice.lines:
        qty = _qty_label(line)
        data.append(
            [
                _kind_label(line.get("kind", "")),
                qty,
                f"{line.get('unit_price', 0):.2f} {invoice.currency}",
                f"{line.get('amount', 0):.2f} {invoice.currency}",
            ]
        )
    table = Table(data, colWidths=[60 * mm, 40 * mm, 35 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0A0B0F")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    totals = [
        ["Sous-total", f"{invoice.subtotal:.2f} {invoice.currency}"],
        ["TVA", f"{invoice.vat:.2f} {invoice.currency}"],
        ["Total", f"{invoice.total:.2f} {invoice.currency}"],
    ]
    t2 = Table(totals, colWidths=[120 * mm, 50 * mm])
    t2.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
            ]
        )
    )
    story.append(t2)

    doc.build(story)
    return buf.getvalue()


def _fmt(dt: datetime | None) -> str:
    return dt.strftime("%d/%m/%Y") if dt else "—"


def _kind_label(kind: str) -> str:
    return {
        "transcribe": "Transcription audio",
        "sheet": "Fiche de révision",
        "quiz": "Quiz",
    }.get(kind, kind)


def _qty_label(line: dict) -> str:
    kind = line.get("kind", "")
    if kind == "transcribe":
        return f"{line.get('audio_minutes', 0)} min"
    return f"{line.get('calls', 0)}"
