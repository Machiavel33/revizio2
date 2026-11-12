"""Transcription locale via faster-whisper (open source, gratuit, offline).

Deux usages :
- Batch : transcription complète d'un fichier audio (worker).
- Pseudo-live : transcription par fenêtres glissantes (WS live).

Le modèle est chargé une fois (singleton) et réutilisé. Taille configurable
via WHISPER_MODEL (tiny/base/small/medium/large-v3). 'small' = bon compromis FR.
"""

import io
import logging
import threading

import numpy as np

from app.core.config import settings

logger = logging.getLogger("revizio.whisper")

_model = None
_model_lock = threading.Lock()


def _get_model():
    """Charge le modèle faster-whisper (singleton, thread-safe)."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel

                logger.info("Chargement du modèle Whisper '%s'…", settings.whisper_model)
                _model = WhisperModel(
                    settings.whisper_model,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                )
                logger.info("Modèle Whisper chargé.")
    return _model


def _decode_audio(audio_bytes: bytes) -> np.ndarray:
    """Décode un blob audio (wav/webm/opus/mp3) en PCM float32 mono 16 kHz."""
    import av  # PyAV (dépendance de faster-whisper)

    container = av.open(io.BytesIO(audio_bytes))
    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="flt", layout="mono", rate=16000)
    frames = []
    for frame in container.decode(stream):
        for rf in resampler.resample(frame):
            frames.append(rf.to_ndarray().reshape(-1))
    if not frames:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(frames).astype(np.float32)


def transcribe_bytes(audio_bytes: bytes, language: str = "fr") -> dict:
    """Transcrit un blob audio complet (batch). Retourne {text, segments, model}."""
    model = _get_model()
    audio = _decode_audio(audio_bytes)
    if audio.size == 0:
        return {"text": "", "segments": [], "model": settings.whisper_model}

    segments, _info = model.transcribe(
        audio,
        language=language,
        vad_filter=True,
        beam_size=5,
    )
    seg_list = []
    texts = []
    for seg in segments:
        seg_list.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        texts.append(seg.text.strip())
    return {
        "text": " ".join(texts).strip(),
        "segments": seg_list,
        "model": settings.whisper_model,
    }


def transcribe_pcm16(pcm_bytes: bytes, language: str = "fr") -> str:
    """Transcrit un chunk PCM16 mono 16 kHz (pseudo-live). Retourne le texte."""
    model = _get_model()
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if audio.size < 1600:  # < 100 ms : trop court
        return ""
    segments, _info = model.transcribe(
        audio,
        language=language,
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
    )
    return " ".join(seg.text.strip() for seg in segments).strip()
