"""Tâches Celery : transcription batch et génération de fiche.

Les tâches sont synchrones (Celery) mais réutilisent les services async via
asyncio.run(). Chaque tâche ouvre sa propre session DB.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.core.crypto import decrypt_secret
from app.core.database import AsyncSessionLocal
from app.models import (
    Course,
    Flashcard,
    Job,
    PlatformKey,
    StudySheet,
    Transcript,
    User,
    UserApiKey,
)
from app.services.sheet_generator import generate_sheet
from app.services.transcription import transcribe
from app.workers.celery_app import celery_app

log = logging.getLogger("revizio.worker")


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


async def _get_platform_key(db, provider: str) -> str | None:
    key = await db.scalar(
        select(PlatformKey).where(
            PlatformKey.provider == provider,
            PlatformKey.is_active.is_(True),
        )
    )
    if key is None:
        return None
    return decrypt_secret(key.encrypted_key)


async def _resolve_key(db, user_id: uuid.UUID, provider: str) -> tuple[str | None, str]:
    """Résout la clé selon le mode de l'utilisateur. Retourne (clé, source)."""
    user = await db.get(User, user_id)
    mode = user.key_mode if user else "byok"
    if mode == "platform":
        pk = await _get_platform_key(db, provider)
        if pk:
            return pk, "platform"
        uk = await _get_user_key(db, user_id, provider)
        return (uk, "byok") if uk else (None, "")
    uk = await _get_user_key(db, user_id, provider)
    if uk:
        return uk, "byok"
    pk = await _get_platform_key(db, provider)
    return (pk, "platform") if pk else (None, "")


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

            audio = await _download_audio(course.audio_url)

            # Choix du moteur : local (faster-whisper) ou cloud (deepgram/openai)
            from app.core.config import settings as _settings

            engine = _settings.transcribe_engine
            result = None
            provider = "local"
            key_source = "local"

            if engine in ("auto", "local"):
                try:
                    from app.services import whisper_local

                    result = await asyncio.to_thread(
                        whisper_local.transcribe_bytes, audio, course.language
                    )
                    provider = "local"
                    key_source = "local"
                except Exception as exc:  # noqa: BLE001
                    if engine == "local":
                        raise
                    log.warning("Whisper local indisponible, fallback cloud: %s", exc)

            if result is None:
                # Fallback cloud : deepgram si dispo, sinon openai
                provider = "deepgram"
                api_key, key_source = await _resolve_key(db, course.user_id, "deepgram")
                if api_key is None:
                    provider = "openai"
                    api_key, key_source = await _resolve_key(db, course.user_id, "openai")
                if api_key is None:
                    raise ValueError("Aucune clé API de transcription configurée")
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

            from app.services import usage as usage_svc

            await usage_svc.record_usage(
                db,
                user_id=course.user_id,
                course_id=course_id,
                kind="transcribe",
                provider=provider,
                key_source=key_source,
                audio_seconds=float(course.duration_sec or 0),
            )
            user_obj = await db.get(User, course.user_id)
            if user_obj is not None:
                await usage_svc.maybe_alert_quota(db, user_obj)

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
            api_key, key_source = await _resolve_key(db, course.user_id, "anthropic")
            if api_key is None:
                provider = "openai"
                api_key, key_source = await _resolve_key(db, course.user_id, "openai")
            if api_key is None:
                raise ValueError("Aucune clé API de génération configurée")

            result = await generate_sheet(
                transcript.full_text, provider=provider, api_key=api_key, language=course.language
            )

            sheet = await db.scalar(select(StudySheet).where(StudySheet.course_id == course_id))
            if sheet is None:
                sheet = StudySheet(course_id=course_id, user_id=course.user_id)
                db.add(sheet)
                await db.flush()
            sheet.content = result["content"]
            sheet.model = result["model"]
            sheet.title = result["content"].get("title", course.title)
            sheet.subject = course.subject
            sheet.tags = course.tags or []

            from app.services import usage as usage_svc

            in_tokens = max(len(transcript.full_text) // 4, 1)
            out_tokens = max(len(str(result["content"])) // 4, 1)
            await usage_svc.record_usage(
                db,
                user_id=course.user_id,
                course_id=course_id,
                kind="sheet",
                provider=provider,
                key_source=key_source,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
            user_obj = await db.get(User, course.user_id)
            if user_obj is not None:
                await usage_svc.maybe_alert_quota(db, user_obj)

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


async def _run_and_dispose(coro) -> None:
    """Exécute une coroutine puis dispose l'engine (évite le conflit de boucle
    asyncio entre tâches Celery successives)."""
    from app.core.database import engine

    try:
        await coro
    finally:
        await engine.dispose()


@celery_app.task(name="revizio.transcribe")
def transcribe_task(course_id: str, job_id: str) -> None:
    asyncio.run(
        _run_and_dispose(_run_transcribe(uuid.UUID(course_id), uuid.UUID(job_id)))
    )


@celery_app.task(name="revizio.generate_sheet")
def generate_sheet_task(course_id: str, job_id: str) -> None:
    asyncio.run(
        _run_and_dispose(_run_generate_sheet(uuid.UUID(course_id), uuid.UUID(job_id)))
    )
