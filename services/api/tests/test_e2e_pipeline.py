"""Test E2E backend : flux complet d'un cours, providers IA mockés.

Parcourt : register → BYOK → create course → upload audio → process →
transcription (mockée) → génération de fiche (mockée) → lecture de la fiche.
"""

import io

import pytest
from sqlalchemy import select

from app.models import Course, Job, StudySheet, Transcript
from app.workers import tasks


@pytest.fixture
def mock_ai(monkeypatch):
    """Remplace les appels réseau IA par des réponses déterministes."""

    async def fake_transcribe(audio, provider, api_key, language="fr", filename="audio.wav"):
        return {
            "text": "La Constitution est la norme suprême. Elle organise les pouvoirs publics.",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": "La Constitution est la norme suprême."},
                {"start": 3.0, "end": 6.0, "text": "Elle organise les pouvoirs publics."},
            ],
            "model": "whisper-1",
        }

    async def fake_generate_sheet(
        transcript, provider, api_key, language="fr", subject=None, domain_key=None
    ):
        return {
            "content": {
                "title": "Droit constitutionnel — la Constitution",
                "summary": "La Constitution est la norme suprême qui organise les pouvoirs.",
                "key_concepts": [
                    {"term": "Constitution", "definition": "Norme suprême de l'ordre juridique."}
                ],
                "sections": [
                    {"heading": "Hiérarchie des normes", "points": ["La Constitution prime."]}
                ],
                "flashcards": [
                    {"question": "Qu'est-ce que la Constitution ?", "answer": "La norme suprême."}
                ],
                "review_questions": ["Pourquoi la Constitution est-elle suprême ?"],
                "estimated_review_time_min": 10,
            },
            "model": "claude-3-5-sonnet-latest",
        }

    async def fake_download(url):
        return b"RIFF....WAVEfake-audio-bytes"

    monkeypatch.setattr(tasks, "transcribe", fake_transcribe)
    monkeypatch.setattr(tasks, "generate_sheet", fake_generate_sheet)
    monkeypatch.setattr(tasks, "_download_audio", fake_download)


@pytest.mark.asyncio
async def test_full_course_pipeline(client, session_factory, mock_ai, monkeypatch):
    # 1. Inscription
    reg = await client.post(
        "/api/auth/register",
        json={"email": "e2e@example.com", "password": "password123", "display_name": "E2E"},
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    # 2. BYOK : clés OpenAI + Anthropic
    for provider, key in [("openai", "sk-test-openai-123456"), ("anthropic", "sk-ant-test-123456")]:
        r = await client.post(
            "/api/api-keys",
            json={"provider": provider, "api_key": key, "is_default": True},
            headers=headers,
        )
        assert r.status_code == 201

    # 3. Création du cours
    course = await client.post(
        "/api/courses",
        json={"title": "Droit constitutionnel", "subject": "Droit"},
        headers=headers,
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    # 4. Upload audio (mock S3 via monkeypatch du service storage)
    from app.api.routes import courses as courses_route

    monkeypatch.setattr(
        courses_route,
        "upload_audio",
        lambda key, data, content_type="audio/wav": f"http://s3/{key}",
    )
    files = {"file": ("cours.wav", io.BytesIO(b"fake-audio"), "audio/wav")}
    up = await client.post(f"/api/courses/{course_id}/audio", files=files, headers=headers)
    assert up.status_code == 200
    assert up.json()["audio_url"] is not None

    # 5. Process : tâches Celery mockées. On capture les coroutines puis on les
    #    exécute séquentiellement (transcribe puis generate_sheet), comme Celery.
    import uuid as _uuid

    from app.workers import tasks as tasks_mod

    monkeypatch.setattr(tasks_mod, "AsyncSessionLocal", session_factory)

    pending: list = []

    def run_transcribe(cid, jid):
        pending.append(tasks_mod._run_transcribe(_uuid.UUID(cid), _uuid.UUID(jid)))

    def run_sheet(cid, jid):
        pending.append(tasks_mod._run_generate_sheet(_uuid.UUID(cid), _uuid.UUID(jid)))

    monkeypatch.setattr(tasks_mod.transcribe_task, "delay", run_transcribe)
    monkeypatch.setattr(tasks_mod.generate_sheet_task, "delay", run_sheet)

    proc = await client.post(f"/api/courses/{course_id}/process", headers=headers)
    assert proc.status_code == 202

    # Exécution séquentielle des tâches capturées
    for coro in pending:
        await coro

    # 6. Vérifie la transcription et la fiche en base
    import uuid as _uuid2

    course_uuid = _uuid2.UUID(course_id)
    async with session_factory() as db:
        transcript = await db.scalar(select(Transcript).where(Transcript.course_id == course_uuid))
        assert transcript is not None
        assert "Constitution" in transcript.full_text
        sheet = await db.scalar(select(StudySheet).where(StudySheet.course_id == course_uuid))
        assert sheet is not None
        assert sheet.content["title"].startswith("Droit constitutionnel")
        assert len(sheet.content["flashcards"]) == 1

        course_row = await db.get(Course, course_uuid)
        assert course_row.status == "ready"

        jobs = (await db.scalars(select(Job).where(Job.course_id == course_uuid))).all()
        assert all(j.status == "done" for j in jobs)
    detail = await client.get(f"/api/courses/{course_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "ready"
    assert body["study_sheet"]["content"]["summary"]
    assert body["transcript"]["full_text"]
