"""Tests du transport résilient (protocole binaire + assembler)."""

import uuid

import pytest

from app.transport import (
    ChunkAssembler,
    ChunkEnd,
    ProtocolError,
    decode_frame,
    encode_frame,
)
from app.transport.protocol import (
    FRAME_BYTES,
    FRAME_SAMPLES,
    FRAMES_PER_CHUNK,
    chunk_end_message,
    pcm_sha256,
)


def _pcm(samples: int = FRAME_SAMPLES) -> bytes:
    return b"\x01\x02" * samples


def test_encode_decode_roundtrip():
    sid = uuid.uuid4()
    frame = encode_frame(sid, 5, _pcm())
    decoded = decode_frame(frame)
    assert decoded.session_id == sid
    assert decoded.frame_seq == 5
    assert decoded.sample_count == FRAME_SAMPLES
    assert decoded.chunk_seq == 0


def test_decode_rejects_bad_magic():
    sid = uuid.uuid4()
    frame = bytearray(encode_frame(sid, 0, _pcm()))
    frame[0:4] = b"XXXX"
    with pytest.raises(ProtocolError) as exc:
        decode_frame(bytes(frame))
    assert exc.value.code == "invalid_frame"


def test_decode_rejects_bad_sample_offset():
    sid = uuid.uuid4()
    frame = encode_frame(sid, 3, _pcm(), sample_offset=999)
    with pytest.raises(ProtocolError):
        decode_frame(frame)


def test_assembler_full_chunk():
    sid = uuid.uuid4()
    asm = ChunkAssembler()
    parts = []
    for seq in range(FRAMES_PER_CHUNK):
        pcm = _pcm()
        parts.append(pcm)
        asm.add(decode_frame(encode_frame(sid, seq, pcm)))
    sha = pcm_sha256(parts)
    end = ChunkEnd.model_validate(
        chunk_end_message(0, FRAMES_PER_CHUNK, FRAME_SAMPLES * FRAMES_PER_CHUNK, sha)
    )
    chunk = asm.take(end)
    assert chunk.chunk_seq == 0
    assert chunk.sha256 == sha
    assert len(chunk.pcm) == FRAME_BYTES * FRAMES_PER_CHUNK


def test_assembler_detects_missing_frames():
    sid = uuid.uuid4()
    asm = ChunkAssembler()
    # Ajoute toutes les trames sauf une
    for seq in range(FRAMES_PER_CHUNK - 1):
        asm.add(decode_frame(encode_frame(sid, seq, _pcm())))
    end = ChunkEnd.model_validate(
        chunk_end_message(0, FRAMES_PER_CHUNK, FRAME_SAMPLES * FRAMES_PER_CHUNK, "0" * 64)
    )
    with pytest.raises(ProtocolError) as exc:
        asm.take(end)
    assert exc.value.code == "missing_frames"
    assert exc.value.missing == [FRAMES_PER_CHUNK - 1]


def test_assembler_detects_sha_mismatch():
    sid = uuid.uuid4()
    asm = ChunkAssembler()
    for seq in range(FRAMES_PER_CHUNK):
        asm.add(decode_frame(encode_frame(sid, seq, _pcm())))
    end = ChunkEnd.model_validate(
        chunk_end_message(0, FRAMES_PER_CHUNK, FRAME_SAMPLES * FRAMES_PER_CHUNK, "f" * 64)
    )
    with pytest.raises(ProtocolError) as exc:
        asm.take(end)
    assert exc.value.code == "invalid_frame"


def test_assembler_integrity_conflict():
    sid = uuid.uuid4()
    asm = ChunkAssembler()
    asm.add(decode_frame(encode_frame(sid, 0, _pcm())))
    # Même frame_seq, contenu différent
    with pytest.raises(ProtocolError) as exc:
        asm.add(decode_frame(encode_frame(sid, 0, b"\x03\x04" * FRAME_SAMPLES)))
    assert exc.value.code == "integrity_conflict"
