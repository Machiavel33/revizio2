"""Sécurité : hachage de mot de passe et JWT (access + refresh).

Utilise PyJWT (maintenu activement) plutôt que python-jose (CVE de forge HS256).
L'algorithme est explicitement fixé à HS256 et vérifié au décodage.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Erreur de validation de token (remplace jose.JWTError)."""


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """Décode et valide un JWT. Lève TokenError si invalide/expiré/mauvais type.

    L'algorithme est restreint à HS256 pour empêcher les attaques de confusion
    d'algorithme (alg=none, RS256→HS256).
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except InvalidTokenError as exc:
        raise TokenError(str(exc)) from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError(f"Type de token invalide (attendu: {expected_type})")
    return payload
