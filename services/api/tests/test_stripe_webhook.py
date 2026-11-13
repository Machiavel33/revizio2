"""Tests de sécurité du webhook Stripe et des gardes de paiement."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import stripe_pay


@pytest.fixture
def client():
    return TestClient(app)


def test_webhook_disabled_without_secret(client, monkeypatch):
    """Sans clé OU sans secret de webhook, le webhook refuse (503)."""
    from app.core.config import settings

    # Clé présente mais secret de webhook absent -> refus (anti-faux-paiement).
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    r = client.post("/api/stripe/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert r.status_code == 503


def test_webhook_disabled_without_key(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_x")
    r = client.post("/api/stripe/webhook", content=b"{}", headers={"stripe-signature": "x"})
    assert r.status_code == 503


def test_webhook_enabled_requires_both(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    assert stripe_pay.webhook_enabled() is False
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_x")
    assert stripe_pay.webhook_enabled() is True


def test_webhook_rejects_bad_signature(client, monkeypatch):
    """Avec les deux secrets configurés, une signature invalide -> 400."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_x")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_x")
    r = client.post(
        "/api/stripe/webhook",
        content=b'{"type":"checkout.session.completed"}',
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400
