"""Chiffrement BYOK : AES-256-GCM pour les clés API utilisateur.

La clé maître (BYOK_ENCRYPTION_KEY) est fournie en base64 (32 octets décodés).
Chaque clé API est chiffrée avec un nonce aléatoire de 12 octets.
Format stocké : nonce(12) || ciphertext || tag(16), le tout en BYTEA.
"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

NONCE_SIZE = 12


def _get_master_key() -> bytes:
    raw = settings.byok_encryption_key
    try:
        key = base64.b64decode(raw)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("BYOK_ENCRYPTION_KEY doit être en base64 valide") from exc
    if len(key) != 32:
        raise ValueError(
            f"BYOK_ENCRYPTION_KEY doit décoder vers 32 octets (reçu {len(key)}). "
            "Générer avec: openssl rand -base64 32"
        )
    return key


def encrypt_secret(plaintext: str) -> bytes:
    """Chiffre un secret (clé API) et retourne nonce||ciphertext+tag."""
    aesgcm = AESGCM(_get_master_key())
    nonce = os.urandom(NONCE_SIZE)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct


def decrypt_secret(blob: bytes) -> str:
    """Déchiffre un blob nonce||ciphertext+tag et retourne le secret en clair."""
    if len(blob) < NONCE_SIZE + 16:
        raise ValueError("Blob chiffré invalide (trop court)")
    aesgcm = AESGCM(_get_master_key())
    nonce, ct = blob[:NONCE_SIZE], blob[NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


def mask_secret(plaintext: str) -> str:
    """Retourne une version masquée pour l'affichage (ex: sk-...abcd)."""
    if len(plaintext) <= 8:
        return "****"
    return f"{plaintext[:4]}...{plaintext[-4:]}"
