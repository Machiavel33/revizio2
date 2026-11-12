"""Assemblage côté serveur des trames d'une connexion en fragments de 10 s.

Le tampon est propre à une connexion WSS : à la déconnexion, les fragments non clos
sont perdus côté serveur, et c'est voulu. Le client garde toutes les trames non
acquittées et les renvoie après reconnexion (ADR-002).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .protocol import (
    BYTES_PER_SAMPLE,
    CHUNK_SAMPLES,
    FRAME_BYTES,
    ChunkEnd,
    Frame,
    ProtocolError,
    chunk_sample_offset,
    first_frame_of,
    pcm_sha256,
)


@dataclass(frozen=True, slots=True)
class AssembledChunk:
    chunk_seq: int
    frame_count: int
    sample_offset: int
    sample_count: int
    sha256: str
    pcm: bytes = field(repr=False)

    @property
    def is_short(self) -> bool:
        """Un fragment de moins de 10 s ne peut être que le dernier de la séance."""
        return self.sample_count < CHUNK_SAMPLES


class ChunkAssembler:
    def __init__(self, max_open_chunks: int = 4) -> None:
        self._open: dict[int, dict[int, bytes]] = {}
        self._max_open = max_open_chunks

    @property
    def open_chunks(self) -> list[int]:
        return sorted(self._open)

    def add(self, frame: Frame) -> None:
        frames = self._open.get(frame.chunk_seq)
        if frames is None:
            if len(self._open) >= self._max_open:
                raise ProtocolError(
                    "quota_exceeded",
                    f"plus de {self._max_open} fragments ouverts sans chunk_end",
                    fatal=True,
                )
            frames = self._open[frame.chunk_seq] = {}
        previous = frames.get(frame.frame_seq)
        if previous is not None and previous != frame.pcm:
            del self._open[frame.chunk_seq]
            raise ProtocolError(
                "integrity_conflict",
                f"trame {frame.frame_seq} reçue deux fois avec un contenu différent",
                chunk_seq=frame.chunk_seq,
            )
        frames[frame.frame_seq] = frame.pcm

    def take(self, end: ChunkEnd) -> AssembledChunk:
        """Retire le fragment du tampon et le valide contre ``chunk_end``.

        En cas d'échec, le tampon du fragment est abandonné : le client doit renvoyer
        toutes les trames du fragment, puis un nouveau ``chunk_end``.
        """
        frames = self._open.pop(end.chunk_seq, {})
        first = first_frame_of(end.chunk_seq)
        expected = range(first, first + end.frame_count)
        missing = [seq for seq in expected if seq not in frames]
        if missing:
            raise ProtocolError(
                "missing_frames",
                f"{len(missing)} trame(s) absente(s) du fragment",
                chunk_seq=end.chunk_seq,
                missing=missing,
            )
        extra = sorted(seq for seq in frames if seq not in expected)
        if extra:
            raise ProtocolError(
                "invalid_frame",
                f"trames {extra} au-delà de frame_count={end.frame_count}",
                chunk_seq=end.chunk_seq,
            )
        short = [seq for seq in expected[:-1] if len(frames[seq]) != FRAME_BYTES]
        if short:
            raise ProtocolError(
                "invalid_frame",
                f"trames courtes {short} avant la dernière trame du fragment",
                chunk_seq=end.chunk_seq,
            )
        parts = [frames[seq] for seq in expected]
        sample_count = sum(len(p) for p in parts) // BYTES_PER_SAMPLE
        if end.sample_offset != chunk_sample_offset(end.chunk_seq):
            raise ProtocolError(
                "invalid_frame",
                f"sample_offset {end.sample_offset} ≠ {chunk_sample_offset(end.chunk_seq)}",
                chunk_seq=end.chunk_seq,
            )
        if end.sample_count != sample_count:
            raise ProtocolError(
                "invalid_frame",
                f"sample_count déclaré {end.sample_count} ≠ reçu {sample_count}",
                chunk_seq=end.chunk_seq,
            )
        sha = pcm_sha256(parts)
        if sha != end.sha256:
            raise ProtocolError(
                "invalid_frame",
                "sha256 déclaré différent du PCM reçu",
                chunk_seq=end.chunk_seq,
            )
        return AssembledChunk(
            chunk_seq=end.chunk_seq,
            frame_count=end.frame_count,
            sample_offset=end.sample_offset,
            sample_count=sample_count,
            sha256=sha,
            pcm=b"".join(parts),
        )
