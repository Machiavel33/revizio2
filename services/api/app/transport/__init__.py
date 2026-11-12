"""Transport audio résilient (porté depuis le projet revizio).

Protocole binaire WSS : trames numérotées (frame_seq), fragments de 10 s avec
SHA-256, ACK après commit, réassemblage côté serveur, stockage durable (fsync +
replace atomique). Permet la réémission après coupure réseau sans perte.
"""

from app.transport.assembler import AssembledChunk, ChunkAssembler
from app.transport.protocol import (
    CHUNK_SAMPLES,
    FRAME_SAMPLES,
    FRAMES_PER_CHUNK,
    SAMPLE_RATE,
    ChunkEnd,
    Frame,
    ProtocolError,
    chunk_end_message,
    decode_frame,
    encode_frame,
    session_ready_message,
)
from app.transport.storage import AudioStore, StorageUnavailable

__all__ = [
    "AssembledChunk",
    "ChunkAssembler",
    "ChunkEnd",
    "Frame",
    "ProtocolError",
    "AudioStore",
    "StorageUnavailable",
    "decode_frame",
    "encode_frame",
    "chunk_end_message",
    "session_ready_message",
    "SAMPLE_RATE",
    "FRAME_SAMPLES",
    "FRAMES_PER_CHUNK",
    "CHUNK_SAMPLES",
]
