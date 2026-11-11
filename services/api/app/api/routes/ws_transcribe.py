"""WebSocket : proxy de transcription temps réel.

Le desktop envoie des chunks audio binaires ; le backend les relaie au provider
de transcription streaming (Deepgram) avec la clé BYOK de l'utilisateur, et
renvoie le texte incrémental au client.

Protocole client -> serveur :
  - 1er message texte JSON :
      {"type":"init","provider":"deepgram","language":"fr","token":"<access_jwt>"}
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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.crypto import decrypt_secret
from app.core.database import AsyncSessionLocal
from app.core.security import TokenError, decode_token
from app.models import User, UserApiKey
from app.services.streaming import stream_deepgram

router = APIRouter()


async def _authenticate(token: str) -> tuple[uuid.UUID, str] | None:
    """Valide le JWT et récupère la clé Deepgram BYOK. Retourne (user_id, api_key)."""
    try:
        payload = decode_token(token, expected_type="access")
        user_id = uuid.UUID(payload["sub"])
    except (TokenError, KeyError, ValueError):
        return None

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        key = await db.scalar(
            select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.provider == "deepgram",
            )
        )
        if key is None:
            return None
        return user_id, decrypt_secret(key.encrypted_key)


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

    auth = await _authenticate(init.get("token", ""))
    if auth is None:
        await websocket.send_json(
            {"type": "error", "message": "Auth invalide ou clé Deepgram manquante"}
        )
        await websocket.close(code=1008)
        return

    _user_id, api_key = auth
    language = init.get("language", "fr")
    await websocket.send_json({"type": "ready"})

    async def on_partial(text: str) -> None:
        await websocket.send_json({"type": "partial", "text": text})

    async def on_final(text: str) -> None:
        await websocket.send_json({"type": "final", "text": text})

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
