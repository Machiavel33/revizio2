"""Webhook Stripe : confirme le paiement d'une facture.

Endpoint public (pas d'auth JWT) : la sécurité repose sur la vérification de la
signature Stripe (`Stripe-Signature`). Sur `checkout.session.completed`, la facture
correspondante passe en `paid`.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from app.core.database import AsyncSessionLocal
from app.services import invoices as inv_svc
from app.services import stripe_pay

logger = logging.getLogger("revizio.stripe_webhook")

router = APIRouter(prefix="/stripe", tags=["stripe"])


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict:
    if not stripe_pay.webhook_enabled():
        # Refus si la clé OU le secret de webhook manque : on ne peut pas vérifier
        # la signature, donc on n'accepte aucun événement (anti-faux-paiement).
        raise HTTPException(status_code=503, detail="Webhook Stripe non configuré")
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_pay.verify_webhook(payload, sig)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Signature webhook invalide: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Signature invalide"
        ) from exc

    if event.get("type") == "checkout.session.completed":
        session = (event.get("data") or {}).get("object") or {}
        invoice_id = (session.get("metadata") or {}).get("invoice_id")
        if invoice_id:
            try:
                inv_uuid = uuid.UUID(invoice_id)
            except (ValueError, TypeError):
                logger.warning("invoice_id invalide dans le webhook: %r", invoice_id)
                return {"received": True}
            async with AsyncSessionLocal() as db:
                try:
                    await inv_svc.mark_paid(
                        db,
                        inv_uuid,
                        stripe_session_id=session.get("id"),
                        stripe_payment_intent=session.get("payment_intent"),
                    )
                    await db.commit()
                    logger.info("Facture %s marquée payée (Stripe)", invoice_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Échec marquage facture %s: %s", invoice_id, exc)
    return {"received": True}
