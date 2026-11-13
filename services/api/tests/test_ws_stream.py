"""Tests du proxy WebSocket streaming (/api/ws/stream).

Vérifie l'authentification et la gestion des cas d'erreur sans dépendre d'un
service STT réel (le relais est testé en intégration sur la stack déployée).
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_stream_rejects_missing_init(client):
    """Sans message init valide, la connexion est fermée (code 1003)."""
    with client.websocket_connect("/api/ws/stream") as ws:
        ws.send_text("not json")
        # Le serveur ferme avec 1003 ; la réception lève une exception.
        with pytest.raises(Exception):  # noqa: B017
            ws.receive_text()


def test_stream_rejects_bad_token(client):
    """Un token invalide -> erreur d'auth puis fermeture 1008."""
    with client.websocket_connect("/api/ws/stream") as ws:
        ws.send_text(
            '{"type":"init","course_id":null,"language":"fr","token":"invalid"}'
        )
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Auth invalide" in msg["message"]


def test_stream_rejects_when_stt_not_configured(client, monkeypatch):
    """Sans STT_SERVICE_URL, le proxy refuse proprement (1013)."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "stt_service_url", "")
    # On a besoin d'un token valide : on en fabrique un pour un user inexistant
    # -> l'auth échoue avant d'atteindre le check STT. On teste donc le chemin
    # "non configuré" via un token valide mais user absent = auth fail.
    # Pour isoler le check STT, on mocke _authenticate.
    from app.api.routes import ws_transcribe

    async def fake_auth(token, course_id):
        import uuid

        return uuid.uuid4(), None

    monkeypatch.setattr(ws_transcribe, "_authenticate", fake_auth)
    with client.websocket_connect("/api/ws/stream") as ws:
        ws.send_text('{"type":"init","course_id":null,"language":"fr","token":"x"}')
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "non configuré" in msg["message"]
