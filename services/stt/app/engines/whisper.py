"""Moteur de transcription batch via faster-whisper (open source, offline).

Un pool de modèles (whisper_pool_size) borné par un sémaphore (whisper_max_concurrency)
permet de traiter plusieurs requêtes sans saturer le CPU. Chaque modèle fixe son nombre
de threads CPU (whisper_cpu_threads) pour éviter que N transcriptions se disputent tous
les cœurs (mesuré : docs/BENCHMARK.md du projet principal).
"""

import io
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np

from app.core.config import settings

logger = logging.getLogger("revizio_stt.whisper")

_models: list = []
_models_lock = threading.Lock()
_semaphore: threading.BoundedSemaphore | None = None
_semaphore_lock = threading.Lock()


def _get_semaphore() -> threading.BoundedSemaphore:
    global _semaphore
    if _semaphore is None:
        with _semaphore_lock:
            if _semaphore is None:
                _semaphore = threading.BoundedSemaphore(max(1, settings.whisper_max_concurrency))
    return _semaphore


def _load_models() -> list:
    """Charge le pool de modèles (singleton, thread-safe)."""
    global _models
    if not _models:
        with _models_lock:
            if not _models:
                from faster_whisper import WhisperModel

                logger.info(
                    "Chargement de %d modèle(s) Whisper '%s' (cpu_threads=%d, concurrency=%d)…",
                    settings.whisper_pool_size,
                    settings.whisper_model,
                    settings.whisper_cpu_threads,
                    settings.whisper_max_concurrency,
                )
                for _ in range(max(1, settings.whisper_pool_size)):
                    _models.append(
                        WhisperModel(
                            settings.whisper_model,
                            device=settings.whisper_device,
                            compute_type=settings.whisper_compute_type,
                            cpu_threads=settings.whisper_cpu_threads,
                        )
                    )
                logger.info("Modèle(s) Whisper chargé(s).")
    return _models


@contextmanager
def _acquire_model() -> Iterator:
    """Acquiert le sémaphore puis un modèle du pool (round-robin simple)."""
    sem = _get_semaphore()
    sem.acquire()
    try:
        models = _load_models()
        # Round-robin : on prend le modèle suivant (thread-safe via le sémaphore).
        idx = int(threading.get_ident()) % len(models)
        yield models[idx]
    finally:
        sem.release()


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
    audio = _decode_audio(audio_bytes)
    if audio.size == 0:
        return {"text": "", "segments": [], "model": settings.whisper_model}

    with _acquire_model() as model:
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
    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if audio.size < 1600:  # < 100 ms : trop court
        return ""
    with _acquire_model() as model:
        segments, _info = model.transcribe(
            audio,
            language=language,
            vad_filter=True,
            beam_size=1,
            condition_on_previous_text=False,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
