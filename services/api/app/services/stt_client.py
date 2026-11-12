"""Client du service STT découplé (ou fallback local).

Si `settings.stt_service_url` est défini, la transcription est déléguée au service
STT (faster-whisper batch + sherpa-onnx streaming) via HTTP. Sinon, on retombe sur
le moteur local `whisper_local` (legacy, dans le processus API).

Ce module expose une interface unique utilisée par le worker (batch) et le WS live.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("revizio.stt_client")


def use_remote() -> bool:
    return bool(settings.stt_service_url)


async def transcribe_bytes(audio: bytes, language: str = "fr") -> dict:
    """Transcrit un blob audio complet. Délègue au service STT si configuré."""
    if use_remote():
        url = settings.stt_service_url.rstrip("/") + "/transcribe"
        async with httpx.AsyncClient(timeout=settings.stt_service_timeout) as client:
            resp = await client.post(
                url,
                files={"file": ("audio.bin", audio, "application/octet-stream")},
                data={"language": language},
            )
            resp.raise_for_status()
            return resp.json()

    # Fallback local (legacy)
    import asyncio

    from app.services import whisper_local

    return await asyncio.to_thread(whisper_local.transcribe_bytes, audio, language)


async def transcribe_pcm16(pcm: bytes, language: str = "fr") -> str:
    """Transcrit un chunk PCM16 (pseudo-live). Délègue au service STT si configuré.

    Le service STT n'expose pas d'endpoint PCM16 one-shot : on l'enveloppe en WAV
    pour réutiliser /transcribe (batch). Pour le vrai streaming, voir le WS /stream.
    """
    if use_remote():
        wav = _pcm16_to_wav(pcm)
        result = await transcribe_bytes(wav, language)
        return result.get("text", "")

    import asyncio

    from app.services import whisper_local

    return await asyncio.to_thread(whisper_local.transcribe_pcm16, pcm, language)


def _pcm16_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Enveloppe du PCM16 mono en WAV (en-tête 44 octets)."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()
