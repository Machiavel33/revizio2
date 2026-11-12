"""WebSocket : transcription temps réel PERSISTÉE côté serveur.

Deux moteurs :
- "local" : faster-whisper (open source, gratuit). Pseudo-live par fenêtres.
- "cloud" : Deepgram (BYOK/plateforme). Vrai streaming.

Le texte final est renvoyé au client ET persisté dans le cours (transcript live).

Protocole client -> serveur :
  - 1er message texte JSON :
      {"type":"init","course_id":"<uuid>","language":"fr","token":"<access_jwt>"}
  - messages binaires : chunks audio (PCM16 mono 16 kHz pour local, opus pour cloud)
  - message texte {"type":"stop"} pour terminer

Protocole serveur -> client :
  - {"type":"ready","engine":"local|cloud"}
  - {"type":"partial","text":"..."}
  - {"type":"final","text":"..."}
  - {"type":"error","message":"..."}
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import TokenError, decode_token
from app.models import Course, Transcript, User
from app.services.streaming import stream_deepgram
from app.workers.tasks import _resolve_key

router = APIRouter()

# Fenêtre de transcription locale (secondes d'audio accumulées avant traitement)
LOCAL_WINDOW_SECONDS = 4
PCM16_BYTES_PER_SEC = 16000 * 2  # 16 kHz mono int16


async def _authenticate(
    token: str, course_id: uuid.UUID | None
) -> tuple[uuid.UUID, Course | None] | None:
    """Valide le JWT et vérifie le cours (appartenance)."""
    try:
        payload = decode_token(token, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (TokenError, KeyError, ValueError):
        return None

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        course = None
        if course_id is not None:
            course = await db.get(Course, course_id)
            if course is None or course.user_id != user_id:
                return None
        return user_id, course


async def _append_final_segment(course_id: uuid.UUID, text: str) -> None:
    """Persiste un segment final dans le transcript du cours (live)."""
    async with AsyncSessionLocal() as db:
        transcript = await db.scalar(select(Transcript).where(Transcript.course_id == course_id))
        if transcript is None:
            transcript = Transcript(course_id=course_id, full_text="", segments=[])
            db.add(transcript)
        transcript.full_text = (transcript.full_text + " " + text).strip()
        segs = list(transcript.segments or [])
        segs.append({"text": text, "ts": datetime.now(UTC).isoformat()})
        transcript.segments = segs
        transcript.provider = transcript.provider or "local"
        transcript.model = transcript.model or settings.whisper_model
        await db.commit()


async def _run_local(
    websocket: WebSocket,
    course_id: uuid.UUID | None,
    language: str,
    audio_source,
) -> None:
    """Pseudo-live : accumule le PCM16, transcrit par fenêtres de ~4s."""
    from app.services import whisper_local

    buffer = bytearray()
    window_bytes = LOCAL_WINDOW_SECONDS * PCM16_BYTES_PER_SEC

    async for chunk in audio_source():
        buffer.extend(chunk)
        if len(buffer) < window_bytes:
            continue
        pcm = bytes(buffer)
        buffer.clear()
        try:
            text = await asyncio.to_thread(whisper_local.transcribe_pcm16, pcm, language)
        except Exception as exc:  # noqa: BLE001
            await websocket.send_json({"type": "error", "message": str(exc)})
            continue
        if text:
            await websocket.send_json({"type": "final", "text": text})
            if course_id is not None:
                await _append_final_segment(course_id, text)

    # Traite le reste
    if buffer:
        try:
            text = await asyncio.to_thread(whisper_local.transcribe_pcm16, bytes(buffer), language)
            if text:
                await websocket.send_json({"type": "final", "text": text})
                if course_id is not None:
                    await _append_final_segment(course_id, text)
        except Exception:  # noqa: BLE001
            pass


async def _run_cloud(
    websocket: WebSocket,
    user_id: uuid.UUID,
    course_id: uuid.UUID | None,
    language: str,
    audio_source,
) -> None:
    """Streaming Deepgram (BYOK/plateforme)."""
    async with AsyncSessionLocal() as db:
        api_key, _src = await _resolve_key(db, user_id, "deepgram")
    if api_key is None:
        await websocket.send_json(
            {"type": "error", "message": "Aucune clé Deepgram (BYOK ou plateforme)"}
        )
        return

    async def on_partial(text: str) -> None:
        await websocket.send_json({"type": "partial", "text": text})

    async def on_final(text: str) -> None:
        await websocket.send_json({"type": "final", "text": text})
        if course_id is not None:
            await _append_final_segment(course_id, text)

    await stream_deepgram(
        audio_source(),
        api_key=api_key,
        language=language,
        on_partial=on_partial,
        on_final=on_final,
    )


async def _run_resilient(
    websocket: WebSocket,
    course_id: uuid.UUID | None,
    language: str,
) -> None:
    """Mode protocole résilient : trames numérotées → fragments 10s → ACK après commit.

    Le client garde les trames non acquittées et les réémet après reconnexion.
    Chaque fragment validé (SHA-256) est transcrit (Whisper local) et persisté,
    puis acquitté. L'idempotence est garantie par chunk_seq : un fragment déjà
    traité est ré-acquitté sans retraitement.
    """
    from app.transport import (
        ChunkAssembler,
        ChunkEnd,
        ProtocolError,
        decode_frame,
        session_ready_message,
    )

    await websocket.send_json(session_ready_message(live_admission=True))

    assembler = ChunkAssembler()
    processed: set[int] = set()

    async def transcribe_and_persist(pcm: bytes) -> str:
        from app.services import whisper_local

        text = await asyncio.to_thread(whisper_local.transcribe_pcm16, pcm, language)
        if text and course_id is not None:
            await _append_final_segment(course_id, text)
        return text

    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return
        if message.get("bytes") is not None:
            try:
                frame = decode_frame(message["bytes"])
                assembler.add(frame)
            except ProtocolError as exc:
                await websocket.send_json(exc.to_message())
                if exc.fatal:
                    return
            continue
        if message.get("text"):
            try:
                ctrl = json.loads(message["text"])
            except json.JSONDecodeError:
                continue
            if ctrl.get("type") == "stop":
                return
            if ctrl.get("type") == "chunk_end":
                try:
                    end = ChunkEnd.model_validate(ctrl)
                except Exception:  # noqa: BLE001
                    await websocket.send_json(
                        {"type": "error", "code": "invalid_frame", "detail": "chunk_end invalide"}
                    )
                    continue
                # Idempotence : fragment déjà traité → ré-ACK sans retraitement
                if end.chunk_seq in processed:
                    await websocket.send_json(
                        {"type": "chunk_ack", "chunk_seq": end.chunk_seq, "duplicate": True}
                    )
                    continue
                try:
                    chunk = assembler.take(end)
                except ProtocolError as exc:
                    await websocket.send_json(exc.to_message())
                    continue
                text = await transcribe_and_persist(chunk.pcm)
                processed.add(end.chunk_seq)
                # ACK APRÈS persistance (pas d'ACK prématuré).
                # Le client peut s'être déconnecté pendant la transcription (lente sous
                # charge) : l'audio est déjà persisté, on sort proprement sans ACK.
                try:
                    await websocket.send_json(
                        {
                            "type": "chunk_ack",
                            "chunk_seq": end.chunk_seq,
                            "text": text,
                            "sha256": chunk.sha256,
                        }
                    )
                except (WebSocketDisconnect, RuntimeError):
                    return


@router.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        init_raw = await websocket.receive_text()
        init = json.loads(init_raw)
    except (WebSocketDisconnect, json.JSONDecodeError):
        await websocket.close(code=1003)
        return

    if init.get("type") != "init":
        await websocket.send_json({"type": "error", "message": "Message init attendu"})
        await websocket.close(code=1003)
        return

    course_id: uuid.UUID | None = None
    if init.get("course_id"):
        try:
            course_id = uuid.UUID(init["course_id"])
        except (ValueError, TypeError):
            course_id = None

    auth = await _authenticate(init.get("token", ""), course_id)
    if auth is None:
        await websocket.send_json(
            {"type": "error", "message": "Auth invalide ou cours introuvable"}
        )
        await websocket.close(code=1008)
        return

    user_id, _course = auth
    language = init.get("language", "fr")

    # Mode protocole résilient (trames numérotées + ACK après commit)
    if init.get("protocol") == "rvzf-v1":
        await _run_resilient(websocket, course_id, language)
        return

    # Choix du moteur
    engine = settings.transcribe_engine
    if engine == "auto":
        engine = "local"  # local par défaut (gratuit) ; fallback cloud géré plus bas

    await websocket.send_json({"type": "ready", "engine": engine})

    async def audio_source():
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                yield message["bytes"]
            elif message.get("text"):
                try:
                    ctrl = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if ctrl.get("type") == "stop":
                    return

    try:
        if engine == "local":
            await _run_local(websocket, course_id, language, audio_source)
        else:
            await _run_cloud(websocket, user_id, course_id, language, audio_source)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except RuntimeError:
            pass
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
