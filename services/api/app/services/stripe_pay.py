"""Intégration Stripe : paiement en ligne des factures.

- `create_checkout_session` : crée une session Stripe Checkout pour une facture.
- `verify_webhook` : vérifie la signature d'un événement Stripe.
- `handle_event` : traite `checkout.session.completed` -> marque la facture payée.

Si `stripe_secret_key` n'est pas configuré, le paiement en ligne est désactivé
(les factures restent payables hors ligne, marquées manuellement par l'admin).
"""

import logging

from app.core.config import settings

logger = logging.getLogger("revizio.stripe")


def enabled() -> bool:
    """Paiement en ligne activé (clé secrète Stripe présente)."""
    return bool(settings.stripe_secret_key)


def webhook_enabled() -> bool:
    """Webhook activé : exige AUSSI le secret de signature (sinon on refuse).

    Sans secret de webhook, la vérification de signature est impossible : on
    refuse de traiter l'événement plutôt que de risquer d'accepter un faux
    paiement (défense en profondeur).
    """
    return bool(settings.stripe_secret_key and settings.stripe_webhook_secret)


def _client():
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def create_checkout_session(
    invoice_id: str,
    invoice_number: str,
    amount: float,
    currency: str,
    customer_email: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Crée une session Stripe Checkout et retourne l'URL de paiement."""
    stripe = _client()
    # Stripe attend des centimes (entier).
    unit_amount = int(round(amount * 100))
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=customer_email,
        line_items=[
            {
                "price_data": {
                    "currency": currency.lower(),
                    "product_data": {"name": f"Facture {invoice_number}"},
                    "unit_amount": unit_amount,
                },
                "quantity": 1,
            }
        ],
        metadata={"invoice_id": invoice_id, "invoice_number": invoice_number},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    """Vérifie la signature Stripe et retourne l'événement décodé."""
    stripe = _client()
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )
