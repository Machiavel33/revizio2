"""Moteur de transcription streaming via sherpa-onnx (transducer zipformer FR).

Vrai temps réel : un flux par séance, décodage incrémental, partial/final avec
offsets en échantillons. Porté de la référence `revizio` (packages/transport/stt.py).

Le modèle (sherpa-onnx-streaming-zipformer-fr-2023-04-14, Apache-2.0) est chargé
depuis un dossier épinglé et vérifié hors ligne (jamais téléchargé au démarrage).
"""

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("revizio_stt.sherpa")

SAMPLE_RATE = 16_000
FRAME_SAMPLES = 4_000  # 250 ms (aligné sur le protocole RVZF v1)


@dataclass(frozen=True, slots=True)
class TranscriptEvent:
    kind: str  # "partial" | "final"
    session_id: uuid.UUID
    start_sample: int
    end_sample: int
    text: str

    def to_message(self) -> dict[str, Any]:
        return {
            "type": f"transcript.{self.kind}",
            "session_id": str(self.session_id),
            "start_sample": self.start_sample,
            "end_sample": self.end_sample,
            "text": self.text,
        }


@dataclass(slots=True)
class _SessionStream:
    stream: Any
    segment_start: int
    next_frame_seq: int
    fed_samples: int = 0
    last_text: str = ""


class SherpaEngine:
    """Reconnaissance streaming sherpa-onnx (transducer), un flux par séance."""

    def __init__(
        self,
        model_dir: Path,
        *,
        num_threads: int = 1,
        int8: bool = True,
        recognizer: Any | None = None,
    ) -> None:
        self._sessions: dict[uuid.UUID, _SessionStream] = {}
        self._recognizer = recognizer or self._load(model_dir, num_threads, int8)

    @staticmethod
    def _load(model_dir: Path, num_threads: int, int8: bool) -> Any:
        import sherpa_onnx

        suffix = ".int8.onnx" if int8 else ".onnx"

        def pick(prefix: str) -> str:
            found = sorted(model_dir.glob(f"{prefix}-*{suffix}"))
            if not found:
                raise FileNotFoundError(f"{prefix}*{suffix} introuvable dans {model_dir}")
            return str(found[0])

        return sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(model_dir / "tokens.txt"),
            encoder=pick("encoder"),
            decoder=pick("decoder"),
            joiner=pick("joiner"),
            num_threads=num_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            enable_endpoint_detection=True,
        )

    def _new(self, frame_seq: int) -> _SessionStream:
        return _SessionStream(
            self._recognizer.create_stream(),
            segment_start=frame_seq * FRAME_SAMPLES,
            next_frame_seq=frame_seq,
        )

    def _decode(self, s: _SessionStream) -> str:
        while self._recognizer.is_ready(s.stream):
            self._recognizer.decode_stream(s.stream)
        text: str = self._recognizer.get_result(s.stream)
        return text.strip()

    def _flush(self, session_id: uuid.UUID, s: _SessionStream) -> list[TranscriptEvent]:
        """Termine le flux courant et émet le dernier segment s'il n'est pas vide."""
        import numpy as np

        s.stream.accept_waveform(SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, dtype=np.float32))
        s.stream.input_finished()
        text = self._decode(s)
        if not text:
            return []
        end = s.segment_start + s.fed_samples
        return [TranscriptEvent("final", session_id, s.segment_start, end, text)]

    def feed(self, session_id: uuid.UUID, frame_seq: int, pcm16: bytes) -> list[TranscriptEvent]:
        """Injecte une trame PCM16 (4000 échantillons) et retourne les événements."""
        import numpy as np

        events: list[TranscriptEvent] = []
        s = self._sessions.get(session_id)
        # Trou de trames (coupure réseau) : clôt le segment, redémarre un flux neuf.
        if s is not None and frame_seq != s.next_frame_seq:
            events += self._flush(session_id, s)
            s = None
        if s is None:
            s = self._sessions[session_id] = self._new(frame_seq)

        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        s.stream.accept_waveform(SAMPLE_RATE, audio)
        s.fed_samples += audio.size
        s.next_frame_seq = frame_seq + 1

        text = self._decode(s)
        if text and text != s.last_text:
            s.last_text = text
            end = s.segment_start + s.fed_samples
            events.append(TranscriptEvent("partial", session_id, s.segment_start, end, text))
        # Endpoint détecté (silence) : émet un final et repart.
        if self._recognizer.is_endpoint(s.stream):
            self._recognizer.reset(s.stream)
            if text:
                end = s.segment_start + s.fed_samples
                events.append(TranscriptEvent("final", session_id, s.segment_start, end, text))
            s.segment_start += s.fed_samples
            s.fed_samples = 0
            s.last_text = ""
        return events

    def close_session(self, session_id: uuid.UUID) -> list[TranscriptEvent]:
        s = self._sessions.pop(session_id, None)
        if s is None:
            return []
        return self._flush(session_id, s)


_engine: SherpaEngine | None = None


def get_engine() -> SherpaEngine | None:
    """Retourne le moteur streaming (singleton), ou None si désactivé/indisponible."""
    global _engine
    if not settings.sherpa_enabled:
        return None
    if _engine is None:
        model_dir = Path(settings.sherpa_model_dir)
        if not model_dir.is_dir():
            logger.warning("Modèle sherpa introuvable: %s (streaming désactivé)", model_dir)
            return None
        try:
            _engine = SherpaEngine(
                model_dir,
                num_threads=settings.sherpa_num_threads,
                int8=settings.sherpa_int8,
            )
            logger.info("Moteur sherpa-onnx streaming chargé (%s).", model_dir.name)
        except Exception as exc:  # noqa: BLE001
            logger.error("Échec chargement sherpa-onnx: %s", exc)
            return None
    return _engine
