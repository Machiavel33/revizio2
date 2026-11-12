"""Service 2FA TOTP (facultatif, opt-in).

- Le secret TOTP est chiffré AES-256-GCM au repos (même clé maître que BYOK).
- Les backup codes sont hachés (bcrypt) et à usage unique.
- Compatible Google Authenticator / Authy / 1Password (RFC 6238, SHA1, 6 chiffres).
"""

import secrets

import pyotp
from passlib.context import CryptContext

from app.core.crypto import decrypt_secret, encrypt_secret

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ISSUER = "Revizio"
BACKUP_CODE_COUNT = 8


def generate_secret() -> str:
    """Génère un secret TOTP base32."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, email: str) -> str:
    """URI otpauth:// pour QR code / import manuel."""
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=ISSUER)


def verify_code(secret: str, code: str) -> bool:
    """Vérifie un code TOTP (tolérance ±1 fenêtre de 30s)."""
    if not code or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def encrypt_totp_secret(secret: str) -> bytes:
    return encrypt_secret(secret)


def decrypt_totp_secret(blob: bytes) -> str:
    return decrypt_secret(blob)


def generate_backup_codes() -> tuple[list[str], list[str]]:
    """Retourne (codes_en_clair, codes_hachés). Les codes en clair ne sont montrés qu'une fois."""
    plain = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(BACKUP_CODE_COUNT)]
    hashed = [pwd_context.hash(c) for c in plain]
    return plain, hashed


def verify_backup_code(code: str, hashed_codes: list[str]) -> int | None:
    """Retourne l'index du code correspondant (à consommer) ou None."""
    for i, h in enumerate(hashed_codes):
        if pwd_context.verify(code, h):
            return i
    return None
