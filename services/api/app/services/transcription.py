"""Service de transcription (batch) via providers BYOK.

Supporte OpenAI (Whisper) et Deepgram. La clé API est déchiffrée à la volée.
"""

import httpx

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"


async def transcribe_openai(
    audio: bytes,
    api_key: str,
    filename: str = "audio.webm",
    model: str = "whisper-1",
    language: str = "fr",
) -> dict:
    """Transcrit via OpenAI Whisper. Retourne {text, segments, model}."""
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, audio, "audio/webm")}
    data = {"model": model, "language": language, "response_format": "verbose_json"}
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(OPENAI_TRANSCRIBE_URL, headers=headers, files=files, data=data)
        resp.raise_for_status()
        payload = resp.json()
    segments = [
        {
            "start": seg.get("start"),
            "end": seg.get("end"),
            "text": seg.get("text", "").strip(),
        }
        for seg in payload.get("segments", [])
    ]
    return {
        "text": payload.get("text", "").strip(),
        "segments": segments,
        "model": model,
    }


async def transcribe_deepgram(
    audio: bytes,
    api_key: str,
    language: str = "fr",
    model: str = "nova-2",
) -> dict:
    """Transcrit via Deepgram. Retourne {text, segments, model}."""
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "audio/webm",
    }
    params = {
        "model": model,
        "language": language,
        "smart_format": "true",
        "punctuate": "true",
    }
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(DEEPGRAM_LISTEN_URL, headers=headers, params=params, content=audio)
        resp.raise_for_status()
        payload = resp.json()

    channels = payload.get("results", {}).get("channels", [])
    alternatives = channels[0].get("alternatives", []) if channels else []
    text = alternatives[0].get("transcript", "").strip() if alternatives else ""
    words = alternatives[0].get("words", []) if alternatives else []
    segments = []
    if words:
        segments = [
            {
                "start": words[0].get("start"),
                "end": words[-1].get("end"),
                "text": text,
            }
        ]
    return {"text": text, "segments": segments, "model": model}


async def transcribe(
    audio: bytes,
    provider: str,
    api_key: str,
    language: str = "fr",
    filename: str = "audio.webm",
) -> dict:
    if provider == "openai":
        return await transcribe_openai(audio, api_key, filename=filename, language=language)
    if provider == "deepgram":
        return await transcribe_deepgram(audio, api_key, language=language)
    raise ValueError(f"Provider de transcription non supporté: {provider}")
