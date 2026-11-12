"""Banc de mesure Revizio — charge bout en bout du transport résilient (RVZF v1).

Mesure, sur la vraie stack (API + worker + Whisper local) :
- latence d'ACK par fragment (p50/p95/max),
- délai audio -> transcript (lag),
- intégrité (SHA-256, fragments acquittés, erreurs),
- débit et pertes.

Usage (dans le conteneur API, qui a websockets/httpx/numpy) :
    python bench_transport.py --sessions 1 --seconds 30 --label cap-1
    python bench_transport.py --sessions 4 --seconds 30 --label cap-4
    python bench_transport.py --sessions 8 --seconds 30 --label cap-8

Le client génère un PCM16 mono 16 kHz synthétique (parole simulée : enveloppe
modulée) — suffisant pour mesurer le transport et le pipeline STT, sans dépendre
d'un corpus externe. Le WER n'est pas mesuré ici (pas de référence).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import statistics
import struct
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np
import websockets

# --- Constantes protocole RVZF v1 (miroir de app/transport/protocol.py) ---
MAGIC = b"RVZF"
PROTOCOL_VERSION = 1
SAMPLE_RATE = 16_000
BYTES_PER_SAMPLE = 2
FRAME_SAMPLES = 4_000
FRAME_BYTES = FRAME_SAMPLES * BYTES_PER_SAMPLE
FRAMES_PER_CHUNK = 40
CHUNK_SAMPLES = FRAME_SAMPLES * FRAMES_PER_CHUNK
HEADER = struct.Struct("<4sBBH16sQQI")
HEADER_SIZE = HEADER.size


def encode_frame(session_id: uuid.UUID, frame_seq: int, pcm: bytes) -> bytes:
    sample_count = len(pcm) // BYTES_PER_SAMPLE
    sample_offset = frame_seq * FRAME_SAMPLES
    header = HEADER.pack(
        MAGIC, PROTOCOL_VERSION, 0, 0, session_id.bytes,
        frame_seq, sample_offset, sample_count,
    )
    return header + pcm


def pcm_sha256(parts: list[bytes]) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()


def chunk_end_message(chunk_seq: int, frame_count: int, sample_count: int, sha256: str) -> dict:
    return {
        "type": "chunk_end",
        "chunk_seq": chunk_seq,
        "frame_count": frame_count,
        "sample_offset": chunk_seq * CHUNK_SAMPLES,
        "sample_count": sample_count,
        "sha256": sha256,
    }


def synth_pcm(seconds: float) -> bytes:
    """PCM16 mono 16 kHz synthétique : parole simulée (enveloppe + formants)."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float32) / SAMPLE_RATE
    # Enveloppe de syllabes (~4 Hz) + porteuses harmoniques
    env = 0.5 * (1 + np.sin(2 * np.pi * 4.0 * t))
    sig = (
        0.4 * np.sin(2 * np.pi * 180 * t)
        + 0.25 * np.sin(2 * np.pi * 320 * t)
        + 0.15 * np.sin(2 * np.pi * 700 * t)
    ) * env
    sig = np.clip(sig, -1.0, 1.0)
    return (sig * 32767).astype(np.int16).tobytes()


@dataclass
class Stats:
    frames_sent: int = 0
    chunks_sent: int = 0
    acks: int = 0
    ack_latencies_ms: list[float] = field(default_factory=list)
    transcript_lags_ms: list[float] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    final_texts: list[str] = field(default_factory=list)
    connected: bool = False


def pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


async def register_and_course(base: str, email: str, password: str) -> tuple[str, str]:
    """Crée un compte + un cours, retourne (access_token, course_id)."""
    async with httpx.AsyncClient(base_url=base, timeout=30) as c:
        r = await c.post("/api/auth/register", json={
            "email": email, "password": password,
            "first_name": "Bench", "last_name": "Load",
        })
        if r.status_code == 409:
            r = await c.post("/api/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        tok = r.json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        r = await c.post("/api/courses", json={"title": "Bench", "language": "fr"}, headers=h)
        r.raise_for_status()
        return tok, r.json()["id"]


async def run_session(base_ws: str, token: str, course_id: str, pcm: bytes,
                      seconds: float, stats: Stats, grace_s: float = 15.0) -> None:
    """Une séance : envoie les trames en temps réel, mesure ACK et lag transcript."""
    session_id = uuid.uuid4()
    # Découpe en trames de 4000 échantillons
    step = FRAME_BYTES
    frames = [pcm[o:o + step] for o in range(0, len(pcm) - step + 1, step)]
    n_frames = int(seconds * 4)  # 4 trames/s (250 ms)
    frames = [frames[i % len(frames)] for i in range(n_frames)]

    url = f"{base_ws}/api/ws/transcribe"
    async with websockets.connect(url, max_size=None) as ws:
        await ws.send(json.dumps({
            "type": "init", "protocol": "rvzf-v1",
            "course_id": course_id, "language": "fr", "token": token,
        }))
        ready = json.loads(await ws.recv())
        if ready.get("type") != "session.ready":
            stats.errors.append({"stage": "init", "msg": ready})
            return
        stats.connected = True

        sent_at: dict[int, float] = {}
        chunk_frames: list[bytes] = []
        chunk_seq = 0
        t0 = time.monotonic()

        async def reader():
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "chunk_ack":
                        now = time.monotonic()
                        cs = msg["chunk_seq"]
                        if cs in sent_at:
                            stats.ack_latencies_ms.append((now - sent_at[cs]) * 1000)
                        stats.acks += 1
                        if msg.get("text"):
                            stats.final_texts.append(msg["text"])
                    elif msg.get("type") == "error":
                        stats.errors.append(msg)
            except Exception:  # noqa: BLE001
                pass

        reader_task = asyncio.create_task(reader())

        for i, frame in enumerate(frames):
            # Cadence temps réel : 1 trame / 250 ms
            target = t0 + (i + 1) * 0.25
            now = time.monotonic()
            if target > now:
                await asyncio.sleep(target - now)
            await ws.send(encode_frame(session_id, i, frame))
            stats.frames_sent += 1
            chunk_frames.append(frame)
            if len(chunk_frames) == FRAMES_PER_CHUNK:
                sha = pcm_sha256(chunk_frames)
                sc = sum(len(f) for f in chunk_frames) // BYTES_PER_SAMPLE
                sent_at[chunk_seq] = time.monotonic()
                await ws.send(json.dumps(chunk_end_message(chunk_seq, len(chunk_frames), sc, sha)))
                stats.chunks_sent += 1
                chunk_frames = []
                chunk_seq += 1

        # Dernier fragment partiel
        if chunk_frames:
            sha = pcm_sha256(chunk_frames)
            sc = sum(len(f) for f in chunk_frames) // BYTES_PER_SAMPLE
            sent_at[chunk_seq] = time.monotonic()
            await ws.send(json.dumps(chunk_end_message(chunk_seq, len(chunk_frames), sc, sha)))
            stats.chunks_sent += 1

        # Laisse le temps aux ACK finaux (transcription du dernier fragment).
        # Sous charge, Whisper sérialise : la grâce doit couvrir la file d'attente.
        await asyncio.sleep(grace_s)
        try:
            await ws.send(json.dumps({"type": "stop"}))
        except Exception:  # noqa: BLE001
            pass
        reader_task.cancel()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("BENCH_BASE", "http://127.0.0.1:8000"))
    ap.add_argument("--sessions", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--label", default="run")
    ap.add_argument("--grace", type=float, default=15.0,
                    help="attente des ACK finaux (s) ; augmenter sous charge")
    ap.add_argument("--out", type=Path, default=Path("/tmp/bench"))
    a = ap.parse_args()

    base = a.base.rstrip("/")
    base_ws = base.replace("http://", "ws://").replace("https://", "wss://")
    a.out.mkdir(parents=True, exist_ok=True)

    # Un compte + cours par séance (isolation).
    # Le rate-limiter auth (20/min) impose une cadence : on espace les inscriptions.
    creds = []
    for i in range(a.sessions):
        email = f"bench_{a.label}_{i}_{int(time.time())}@example.com"
        tok, cid = await register_and_course(base, email, "BenchPass123!")
        creds.append((tok, cid))
        if i < a.sessions - 1:
            await asyncio.sleep(3.2)  # ~19/min, sous la limite de 20/min

    pcm = synth_pcm(a.seconds + 2)
    stats_list = [Stats() for _ in range(a.sessions)]

    t0 = time.monotonic()
    await asyncio.gather(*(
        run_session(base_ws, tok, cid, pcm, a.seconds, st, grace_s=a.grace)
        for (tok, cid), st in zip(creds, stats_list)
    ), return_exceptions=True)
    wall = time.monotonic() - t0

    ack = [x for st in stats_list for x in st.ack_latencies_ms]
    lag = [x for st in stats_list for x in st.transcript_lags_ms]
    errors = [e for st in stats_list for e in st.errors]
    total_chunks = sum(st.chunks_sent for st in stats_list)
    total_acks = sum(st.acks for st in stats_list)
    connected = sum(1 for st in stats_list if st.connected)

    summary = {
        "label": a.label,
        "sessions": a.sessions,
        "seconds_per_session": a.seconds,
        "wall_s": round(wall, 1),
        "connected": connected,
        "chunks_sent": total_chunks,
        "acks": total_acks,
        "ack_loss": total_chunks - total_acks,
        "ack_p50_ms": round(pct(ack, 50), 1),
        "ack_p95_ms": round(pct(ack, 95), 1),
        "ack_max_ms": round(max(ack), 1) if ack else 0,
        "errors": len(errors),
        "error_samples": errors[:5],
    }
    out_file = a.out / f"stats-{a.label}.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
