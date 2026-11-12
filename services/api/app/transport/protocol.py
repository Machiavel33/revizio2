"""Protocole audio Revizio v1 (docs/10_API_ET_PROTOCOLE.md).

Trame binaire WSS = en-tête fixe little-endian de 44 octets + PCM s16le mono 16 kHz.

    offset  taille  champ
    0       4       magic          b"RVZF"
    4       1       version        1
    5       1       flags          0 (réservé)
    6       2       reserved       0
    8       16      session_id     UUID, octets big-endian (uuid.UUID.bytes)
    24      8       frame_seq      uint64, 0-based
    32      8       sample_offset  uint64, relatif à la séance
    40      4       sample_count   uint32, 1..4000

Invariants imposés par le serveur :
- une trame pleine = 4000 échantillons (250 ms) ; seule la dernière trame de la séance
  peut être plus courte ;
- donc ``sample_offset == frame_seq * 4000`` pour toute trame valide ;
- ``chunk_seq = frame_seq // 40`` ; un fragment nominal = 40 trames = 10 s ;
- le SHA-256 d'un fragment porte sur la concaténation des octets PCM de ses trames,
  dans l'ordre, sans en-tête ni JSON.
"""

from __future__ import annotations

import hashlib
import struct
import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAGIC = b"RVZF"
PROTOCOL_VERSION = 1
SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2
FRAME_SAMPLES = 4_000
FRAME_BYTES = FRAME_SAMPLES * BYTES_PER_SAMPLE
FRAMES_PER_CHUNK = 40
CHUNK_SAMPLES = FRAME_SAMPLES * FRAMES_PER_CHUNK
CHUNK_BYTES = CHUNK_SAMPLES * BYTES_PER_SAMPLE

HEADER = struct.Struct("<4sBBH16sQQI")
HEADER_SIZE = HEADER.size
MAX_FRAME_MESSAGE = HEADER_SIZE + FRAME_BYTES
MAX_TEXT_MESSAGE = 2_048
# 2**40 trames de 250 ms = des millénaires : borne anti-débordement, pas une limite produit.
MAX_FRAME_SEQ = 2**40

ErrorCode = Literal[
    "unauthorized",
    "quota_exceeded",
    "invalid_frame",
    "integrity_conflict",
    "missing_frames",
    "missing_chunks",
    "storage_unavailable",
    "session_closed",
    "live_unavailable",
]


class ProtocolError(Exception):
    """Erreur de protocole remontée au client sous forme de message ``error``."""

    def __init__(
        self,
        code: ErrorCode,
        detail: str,
        *,
        chunk_seq: int | None = None,
        missing: list[int] | None = None,
        fatal: bool = False,
    ) -> None:
        super().__init__(f"{code}: {detail}")
        self.code: ErrorCode = code
        self.detail = detail
        self.chunk_seq = chunk_seq
        self.missing = missing
        self.fatal = fatal

    def to_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"type": "error", "code": self.code, "detail": self.detail}
        if self.chunk_seq is not None:
            msg["chunk_seq"] = self.chunk_seq
        if self.missing is not None:
            msg["missing"] = self.missing
        return msg


@dataclass(frozen=True, slots=True)
class Frame:
    session_id: uuid.UUID
    frame_seq: int
    sample_offset: int
    pcm: bytes = field(repr=False)

    @property
    def sample_count(self) -> int:
        return len(self.pcm) // BYTES_PER_SAMPLE

    @property
    def chunk_seq(self) -> int:
        return chunk_seq_of(self.frame_seq)


def chunk_seq_of(frame_seq: int) -> int:
    return frame_seq // FRAMES_PER_CHUNK


def first_frame_of(chunk_seq: int) -> int:
    return chunk_seq * FRAMES_PER_CHUNK


def chunk_sample_offset(chunk_seq: int) -> int:
    return chunk_seq * CHUNK_SAMPLES


def pcm_sha256(pcm_parts: list[bytes]) -> str:
    h = hashlib.sha256()
    for part in pcm_parts:
        h.update(part)
    return h.hexdigest()


def encode_frame(
    session_id: uuid.UUID,
    frame_seq: int,
    pcm: bytes,
    *,
    sample_offset: int | None = None,
    version: int = PROTOCOL_VERSION,
) -> bytes:
    """Encode une trame. ``sample_offset`` explicite sert uniquement aux tests d'erreur."""
    if not pcm or len(pcm) % BYTES_PER_SAMPLE or len(pcm) > FRAME_BYTES:
        raise ValueError(f"PCM de {len(pcm)} octets : attendu 2..{FRAME_BYTES}, pair")
    if sample_offset is None:
        sample_offset = frame_seq * FRAME_SAMPLES
    header = HEADER.pack(
        MAGIC,
        version,
        0,
        0,
        session_id.bytes,
        frame_seq,
        sample_offset,
        len(pcm) // BYTES_PER_SAMPLE,
    )
    return header + pcm


def decode_frame(data: bytes) -> Frame:
    if len(data) < HEADER_SIZE:
        raise ProtocolError("invalid_frame", "message binaire plus court que l'en-tête", fatal=True)
    if len(data) > MAX_FRAME_MESSAGE:
        raise ProtocolError("invalid_frame", "trame trop grande", fatal=True)
    magic, version, flags, reserved, sid, frame_seq, sample_offset, sample_count = (
        HEADER.unpack_from(data)
    )
    if magic != MAGIC:
        raise ProtocolError("invalid_frame", "magic inconnu", fatal=True)
    if version != PROTOCOL_VERSION:
        raise ProtocolError("invalid_frame", f"version {version} non supportée", fatal=True)
    if flags or reserved:
        raise ProtocolError("invalid_frame", "champs réservés non nuls", fatal=True)
    if not 1 <= sample_count <= FRAME_SAMPLES:
        raise ProtocolError("invalid_frame", f"sample_count {sample_count} hors 1..{FRAME_SAMPLES}")
    if frame_seq >= MAX_FRAME_SEQ:
        raise ProtocolError("invalid_frame", "frame_seq hors bornes")
    pcm = data[HEADER_SIZE:]
    if len(pcm) != sample_count * BYTES_PER_SAMPLE:
        raise ProtocolError("invalid_frame", "taille PCM différente de sample_count")
    if sample_offset != frame_seq * FRAME_SAMPLES:
        raise ProtocolError(
            "invalid_frame",
            f"sample_offset {sample_offset} ≠ attendu {frame_seq * FRAME_SAMPLES}",
        )
    return Frame(uuid.UUID(bytes=sid), frame_seq, sample_offset, pcm)


Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ChunkEnd(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["chunk_end"]
    chunk_seq: Annotated[int, Field(ge=0, lt=MAX_FRAME_SEQ // FRAMES_PER_CHUNK)]
    frame_count: Annotated[int, Field(ge=1, le=FRAMES_PER_CHUNK)]
    sample_offset: Annotated[int, Field(ge=0)]
    sample_count: Annotated[int, Field(ge=1, le=CHUNK_SAMPLES)]
    sha256: Sha256Hex


class Ping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["ping"]


def chunk_end_message(
    chunk_seq: int, frame_count: int, sample_count: int, sha256: str
) -> dict[str, Any]:
    return {
        "type": "chunk_end",
        "chunk_seq": chunk_seq,
        "frame_count": frame_count,
        "sample_offset": chunk_sample_offset(chunk_seq),
        "sample_count": sample_count,
        "sha256": sha256,
    }


def session_ready_message(live_admission: bool) -> dict[str, Any]:
    return {
        "type": "session.ready",
        "protocol_version": PROTOCOL_VERSION,
        "sample_rate": SAMPLE_RATE,
        "frame_samples": FRAME_SAMPLES,
        "frames_per_chunk": FRAMES_PER_CHUNK,
        "max_frame_bytes": MAX_FRAME_MESSAGE,
        "live_admission": live_admission,
    }
