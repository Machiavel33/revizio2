#!/usr/bin/env python
"""Re-chiffrement des clés BYOK avec une nouvelle clé maître (rotation master key).

Usage:
    OLD_BYOK_KEY=<base64_32> NEW_BYOK_KEY=<base64_32> \
        python scripts/rekey_byok.py [--dry-run]

- Déchiffre chaque clé API avec OLD_BYOK_KEY, la re-chiffre avec NEW_BYOK_KEY.
- Transaction unique : tout ou rien.
- --dry-run : compte les clés sans écrire.

Prérequis : DATABASE_URL pointant vers la base cible.
"""

import argparse
import asyncio
import base64
import os
import sys

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Permet l'import du package app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

from app.models import UserApiKey  # noqa: E402

NONCE_SIZE = 12


def _load_key(env_name: str) -> bytes:
    raw = os.environ.get(env_name)
    if not raw:
        raise SystemExit(f"Variable {env_name} manquante")
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise SystemExit(f"{env_name} doit décoder vers 32 octets (reçu {len(key)})")
    return key


def _decrypt(blob: bytes, key: bytes) -> str:
    aesgcm = AESGCM(key)
    nonce, ct = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def _encrypt(plaintext: str, key: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_SIZE)
    return nonce + aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)


async def main(dry_run: bool) -> None:
    old_key = _load_key("OLD_BYOK_KEY")
    new_key = _load_key("NEW_BYOK_KEY")
    if old_key == new_key:
        raise SystemExit("OLD et NEW sont identiques — rien à faire")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL manquant")

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        keys = (await db.scalars(select(UserApiKey))).all()
        print(f"{len(keys)} clé(s) BYOK à re-chiffrer")
        if dry_run:
            print("[dry-run] aucune écriture")
            await engine.dispose()
            return

        for k in keys:
            plaintext = _decrypt(k.encrypted_key, old_key)
            k.encrypted_key = _encrypt(plaintext, new_key)
        await db.commit()
        print(f"OK: {len(keys)} clé(s) re-chiffrée(s) avec la nouvelle clé maître")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
