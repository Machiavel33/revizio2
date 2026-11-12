"""Tâches Celery : transcription batch et génération de fiche.

Les tâches sont synchrones (Celery) mais réutilisent les services async via
asyncio.run(). Chaque tâche ouvre sa propre session DB.
"""

import asyncio
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.core.crypto import decrypt_secret
from app.core.database import AsyncSessionLocal
from app.models import Course, Flashcard, Job, StudySheet, Transcript, UserApiKey
from app.services.sheet_generator import generate_sheet
from app.services.transcription import transcribe
from app.workers.celery_app import celery_app


def _now() -> datetime:
    return datetime.now(UTC)


async def _get_user_key(db, user_id: uuid.UUID, provider: str) -> str | None:
    key = await db.scalar(
        select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.provider == provider,
        )
    )
    if key is None:
        return None
    return decrypt_secret(key.encrypted_key)


async def _download_audio(audio_url: str) -> bytes:
    """Récupère l'audio selon le backend (local:// ou URL S3/HTTP)."""
    from app.services import storage

    if audio_url.startswith("local://"):
        key = storage.key_from_url(audio_url)
        return storage.read_audio(key)
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.get(audio_url)
        resp.raise_for_status()
        return resp.content


async def _run_transcribe(course_id: uuid.UUID, job_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        course = await db.get(Course, course_id)
        if job is None or course is None:
            return
        job.status = "running"
        await db.commit()

        try:
            if not course.audio_url:
                raise ValueError("Aucun audio pour ce cours")

            # Provider de transcription : deepgram si dispo, sinon openai
            provider = "deepgram"
            api_key = await _get_user_key(db, course.user_id, "deepgram")
            if api_key is None:
                provider = "openai"
                api_key = await _get_user_key(db, course.user_id, "openai")
            if api_key is None:
                raise ValueError("Aucune clé API de transcription configurée (BYOK)")

            audio = await _download_audio(course.audio_url)
            result = await transcribe(
                audio, provider=provider, api_key=api_key, language=course.language
            )

            transcript = await db.scalar(
                select(Transcript).where(Transcript.course_id == course_id)
            )
            if transcript is None:
                transcript = Transcript(course_id=course_id)
                db.add(transcript)
            transcript.full_text = result["text"]
            transcript.segments = result["segments"]
            transcript.provider = provider
            transcript.model = result["model"]

            course.status = "generating"
            job.status = "done"
            job.finished_at = _now()
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = _now()
            course.status = "failed"
            await db.commit()


async def _run_generate_sheet(course_id: uuid.UUID, job_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(Job, job_id)
        course = await db.get(Course, course_id)
        if job is None or course is None:
            return
        job.status = "running"
        await db.commit()

        try:
            transcript = await db.scalar(
                select(Transcript).where(Transcript.course_id == course_id)
            )
            if transcript is None or not transcript.full_text:
                raise ValueError("Transcription absente ou vide")

            provider = "anthropic"
            api_key = await _get_user_key(db, course.user_id, "anthropic")
            if api_key is None:
                provider = "openai"
                api_key = await _get_user_key(db, course.user_id, "openai")
            if api_key is None:
                raise ValueError("Aucune clé API de génération configurée (BYOK)")

            result = await generate_sheet(
                transcript.full_text, provider=provider, api_key=api_key, language=course.language
            )

            sheet = await db.scalar(select(StudySheet).where(StudySheet.course_id == course_id))
            if sheet is None:
                sheet = StudySheet(course_id=course_id)
                db.add(sheet)
                await db.flush()
            sheet.content = result["content"]
            sheet.model = result["model"]

            # Remplace les flashcards existantes
            existing = await db.scalars(
                select(Flashcard).where(Flashcard.study_sheet_id == sheet.id)
            )
            for fc in existing:
                await db.delete(fc)
            for item in result["content"].get("flashcards", []):
                db.add(
                    Flashcard(
                        study_sheet_id=sheet.id,
                        question=item.get("question", ""),
                        answer=item.get("answer", ""),
                    )
                )

            course.status = "ready"
            job.status = "done"
            job.finished_at = _now()
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = _now()
            course.status = "failed"
            await db.commit()


@celery_app.task(name="revizio.transcribe")
def transcribe_task(course_id: str, job_id: str) -> None:
    asyncio.run(_run_transcribe(uuid.UUID(course_id), uuid.UUID(job_id)))


@celery_app.task(name="revizio.generate_sheet")
def generate_sheet_task(course_id: str, job_id: str) -> None:
    asyncio.run(_run_generate_sheet(uuid.UUID(course_id), uuid.UUID(job_id)))
