"""WebSocket : transcription temps réel PERSISTÉE côté serveur.

Le desktop envoie des chunks audio binaires ; le backend les relaie au provider
de transcription streaming (Deepgram) avec la clé (BYOK ou plateforme), renvoie
le texte incrémental au client ET persiste chaque segment final dans le cours
(transcript live), pour que le cours s'écrive en direct sur le serveur.

Protocole client -> serveur :
  - 1er message texte JSON :
      {"type":"init","course_id":"<uuid>","language":"fr","token":"<access_jwt>"}
  - messages binaires : chunks audio (webm/opus)
  - message texte {"type":"stop"} pour terminer

Protocole serveur -> client :
  - {"type":"ready"}
  - {"type":"partial","text":"..."}
  - {"type":"final","text":"..."}
  - {"type":"error","message":"..."}
"""

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import TokenError, decode_token
from app.models import Course, Transcript, User
from app.services.streaming import stream_deepgram
from app.workers.tasks import _resolve_key

router = APIRouter()


async def _authenticate(
    token: str, course_id: uuid.UUID | None
) -> tuple[uuid.UUID, str, Course | None] | None:
    """Valide le JWT, résout la clé Deepgram (BYOK/plateforme) et le cours."""
    try:
        payload = decode_token(token, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (TokenError, KeyError, ValueError):
        return None

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        api_key, _src = await _resolve_key(db, user_id, "deepgram")
        if api_key is None:
            return None
        course = None
        if course_id is not None:
            course = await db.get(Course, course_id)
            if course is None or course.user_id != user_id:
                return None
        return user_id, api_key, course


async def _append_final_segment(course_id: uuid.UUID, text: str) -> None:
    """Persiste un segment final dans le transcript du cours (live)."""
    async with AsyncSessionLocal() as db:
        transcript = await db.scalar(
            select(Transcript).where(Transcript.course_id == course_id)
        )
        if transcript is None:
            transcript = Transcript(course_id=course_id, full_text="", segments=[])
            db.add(transcript)
        # Concatène le texte et ajoute le segment horodaté
        transcript.full_text = (transcript.full_text + " " + text).strip()
        segs = list(transcript.segments or [])
        segs.append({"text": text, "ts": datetime.now(UTC).isoformat()})
        transcript.segments = segs
        transcript.provider = transcript.provider or "deepgram"
        transcript.model = transcript.model or "nova-2"
        await db.commit()


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
            {
                "type": "error",
                "message": "Auth invalide, clé Deepgram manquante ou cours introuvable",
            }
        )
        await websocket.close(code=1008)
        return

    _user_id, api_key, _course = auth
    language = init.get("language", "fr")
    await websocket.send_json({"type": "ready"})

    async def on_partial(text: str) -> None:
        await websocket.send_json({"type": "partial", "text": text})

    async def on_final(text: str) -> None:
        # Renvoie au client ET persiste côté serveur (écriture en direct)
        await websocket.send_json({"type": "final", "text": text})
        if course_id is not None:
            await _append_final_segment(course_id, text)

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
        await stream_deepgram(
            audio_source(),
            api_key=api_key,
            language=language,
            on_partial=on_partial,
            on_final=on_final,
        )
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
