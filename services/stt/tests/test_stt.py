"""Tests du service STT : endpoints HTTP + logique sherpa (moteur mocké)."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.engines import sherpa
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_health(client):
    async with client as c:
        r = await c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "whisper_model" in body
    assert "streaming" in body


@pytest.mark.asyncio
async def test_transcribe_empty_file(client):
    async with client as c:
        r = await c.post("/transcribe", files={"file": ("a.wav", b"", "audio/wav")})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_transcribe_ok(client, monkeypatch):
    from app.engines import whisper

    def fake_transcribe(data, language="fr"):
        return {"text": "bonjour", "segments": [], "model": "small"}

    monkeypatch.setattr(whisper, "transcribe_bytes", fake_transcribe)
    async with client as c:
        r = await c.post(
            "/transcribe",
            files={"file": ("a.wav", b"RIFFxxxx", "audio/wav")},
            data={"language": "fr"},
        )
    assert r.status_code == 200
    assert r.json()["text"] == "bonjour"


# --- Sherpa engine (recognizer mocké) ---


class _FakeStream:
    def __init__(self):
        self.fed = 0

    def accept_waveform(self, rate, audio):
        self.fed += len(audio)

    def input_finished(self):
        pass


class _FakeRecognizer:
    def __init__(self):
        self._text = ""
        self._endpoint = False

    def create_stream(self):
        return _FakeStream()

    def is_ready(self, stream):
        return False

    def decode_stream(self, stream):
        pass

    def get_result(self, stream):
        return self._text

    def is_endpoint(self, stream):
        return self._endpoint

    def reset(self, stream):
        self._endpoint = False


def test_sherpa_feed_partial_and_final():
    rec = _FakeRecognizer()
    eng = sherpa.SherpaEngine.__new__(sherpa.SherpaEngine)
    eng._sessions = {}
    eng._recognizer = rec
    sid = uuid.uuid4()
    pcm = b"\x00\x00" * 4000  # 4000 échantillons

    # Pas de texte -> aucun événement
    assert eng.feed(sid, 0, pcm) == []

    # Texte partiel
    rec._text = "bonjour"
    evs = eng.feed(sid, 1, pcm)
    assert len(evs) == 1
    assert evs[0].kind == "partial"
    assert evs[0].text == "bonjour"

    # Endpoint -> final
    rec._endpoint = True
    evs = eng.feed(sid, 2, pcm)
    kinds = [e.kind for e in evs]
    assert "final" in kinds


def test_sherpa_frame_gap_flushes():
    rec = _FakeRecognizer()
    eng = sherpa.SherpaEngine.__new__(sherpa.SherpaEngine)
    eng._sessions = {}
    eng._recognizer = rec
    sid = uuid.uuid4()
    pcm = b"\x00\x00" * 4000

    rec._text = "premier"
    eng.feed(sid, 0, pcm)
    # Saut de frame_seq (coupure) -> flush du segment courant (texte encore "premier")
    evs = eng.feed(sid, 5, pcm)
    assert any(e.kind == "final" and e.text == "premier" for e in evs)


def test_sherpa_close_session():
    rec = _FakeRecognizer()
    eng = sherpa.SherpaEngine.__new__(sherpa.SherpaEngine)
    eng._sessions = {}
    eng._recognizer = rec
    sid = uuid.uuid4()
    pcm = b"\x00\x00" * 4000
    rec._text = "fin"
    eng.feed(sid, 0, pcm)
    evs = eng.close_session(sid)
    assert any(e.kind == "final" for e in evs)
    # Session retirée
    assert eng.close_session(sid) == []


# --- Sécurité : secret partagé + en-têtes ---


@pytest.mark.asyncio
async def test_security_headers_present(client):
    async with client as c:
        r = await c.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_shared_secret_enforced(monkeypatch):
    """Avec un secret configuré, /transcribe exige X-STT-Token."""
    from fastapi import FastAPI

    from app.core import security

    # Reconstruit l'app avec un secret pour ce test.
    test_app = FastAPI()
    test_app.add_middleware(security.SharedSecretMiddleware, secret="s3cret")

    @test_app.get("/protected")
    async def protected():
        return {"ok": True}

    @test_app.get("/health")
    async def health():
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # /health public
        assert (await c.get("/health")).status_code == 200
        # /protected sans token -> 401
        assert (await c.get("/protected")).status_code == 401
        # avec bon token -> 200
        r = await c.get("/protected", headers={"X-STT-Token": "s3cret"})
        assert r.status_code == 200
        # mauvais token -> 401
        r = await c.get("/protected", headers={"X-STT-Token": "wrong"})
        assert r.status_code == 401
