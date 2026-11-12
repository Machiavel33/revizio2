"""Point d'entrée FastAPI — service STT Revizio.

Endpoints :
- POST /transcribe : transcription batch d'un blob audio (faster-whisper).
- WS   /stream     : transcription streaming temps réel (sherpa-onnx), trames PCM16.
- GET  /health     : état du service + moteurs disponibles.
"""

import asyncio
import json
import logging
import uuid

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.core.config import settings
from app.engines import sherpa, whisper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("revizio_stt")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Service de transcription découplé (faster-whisper batch + sherpa-onnx streaming).",
    docs_url=None if settings.is_production else "/docs",
    openapi_url=None if settings.is_production else "/openapi.json",
)


@app.get("/health")
async def health() -> dict:
    engine = sherpa.get_engine()
    return {
        "status": "ok",
        "app": settings.app_name,
        "whisper_model": settings.whisper_model,
        "whisper_concurrency": settings.whisper_max_concurrency,
        "streaming": engine is not None,
    }


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("fr"),
) -> dict:
    """Transcrit un blob audio complet (batch). Retourne {text, segments, model}."""
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {settings.max_upload_bytes // (1024 * 1024)} Mo)",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide")
    try:
        result = await asyncio.to_thread(whisper.transcribe_bytes, data, language)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Échec transcription batch")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription échouée: {exc}",
        ) from exc
    return result


@app.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    """Streaming temps réel : le client envoie des trames PCM16 (4000 échantillons).

    Protocole :
      - 1er message texte JSON : {"type":"init","session_id":"<uuid>","language":"fr"}
      - messages binaires : trames PCM16 mono 16 kHz (4000 échantillons = 8000 octets)
      - message texte {"type":"stop"} pour terminer
    Serveur -> client :
      - {"type":"ready","engine":"sherpa"}
      - {"type":"transcript.partial","text":"..."}
      - {"type":"transcript.final","text":"..."}
      - {"type":"error","message":"..."}
    """
    await websocket.accept()
    engine = sherpa.get_engine()
    if engine is None:
        await websocket.send_json({"type": "error", "message": "Streaming indisponible"})
        await websocket.close(code=1013)
        return

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

    try:
        session_id = uuid.UUID(init["session_id"])
    except (KeyError, ValueError, TypeError):
        await websocket.send_json({"type": "error", "message": "session_id invalide"})
        await websocket.close(code=1003)
        return

    await websocket.send_json({"type": "ready", "engine": "sherpa"})
    frame_seq = 0

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                pcm = message["bytes"]
                try:
                    events = await asyncio.to_thread(engine.feed, session_id, frame_seq, pcm)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Échec streaming")
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    continue
                frame_seq += 1
                for ev in events:
                    await websocket.send_json(ev.to_message())
            elif message.get("text"):
                try:
                    ctrl = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if ctrl.get("type") == "stop":
                    break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            for ev in engine.close_session(session_id):
                await websocket.send_json(ev.to_message())
        except Exception:  # noqa: BLE001
            pass
        try:
            await websocket.close()
        except RuntimeError:
            pass
