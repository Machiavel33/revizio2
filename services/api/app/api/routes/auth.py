"""Routes d'authentification : register, login, refresh, me."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.core.security import (
    TokenError,
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import PasswordResetToken, User
from app.schemas.auth import (
    MfaRequired,
    PasswordForgotIn,
    PasswordResetIn,
    RefreshRequest,
    TokenPair,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.services import audit, mail

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_meta(request: Request) -> dict:
    """Métadonnées de traçabilité (IP, user-agent, origine)."""
    forwarded = request.headers.get("x-forwarded-for")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    return {
        "ip": ip,
        "user_agent": request.headers.get("user-agent", "")[:500],
        "origin": request.headers.get("origin", "")[:200],
        "referer": request.headers.get("referer", "")[:300],
    }


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email",
        )
    # Si une clé plateforme est configurée, le nouvel utilisateur démarre en
    # mode "platform" (zéro config pour lui). Sinon BYOK.
    from app.models import PlatformKey

    has_platform = await db.scalar(
        select(PlatformKey.id).where(PlatformKey.is_active.is_(True)).limit(1)
    )
    full_name = f"{payload.first_name} {payload.last_name}".strip()
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        display_name=payload.display_name or full_name or payload.email.split("@")[0],
        key_mode="platform" if has_platform else "byok",
    )
    db.add(user)
    await db.flush()
    await audit.record(
        db,
        action="user.register",
        actor_id=user.id,
        target=str(user.id),
        metadata={
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            **_client_meta(request),
        },
    )
    mail.send_welcome(user.email, user.display_name)
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenPair | MfaRequired)
async def login(
    payload: UserLogin,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair | MfaRequired:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if (
        user is None
        or user.password_hash is None
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé",
        )
    # 2FA activée : émet un challenge court au lieu des tokens finaux
    if user.totp_enabled:
        await audit.record(
            db,
            action="user.login.mfa_challenge",
            actor_id=user.id,
            target=str(user.id),
            metadata=_client_meta(request),
        )
        return MfaRequired(mfa_token=create_mfa_token(str(user.id)))
    await audit.record(
        db,
        action="user.login",
        actor_id=user.id,
        target=str(user.id),
        metadata=_client_meta(request),
    )
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    payload: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    try:
        data = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide ou expiré",
        ) from exc
    user = await db.get(User, data["sub"])
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou désactivé",
        )
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: PasswordForgotIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    import hashlib
    import secrets
    from datetime import UTC, datetime, timedelta

    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is not None and user.is_active:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await db.flush()
        mail.send_password_reset(user.email, user.display_name, token)
        await audit.record(db, action="user.password.forgot", actor_id=user.id, target=str(user.id))
    return {"detail": "Si un compte existe, un email a été envoyé."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: PasswordResetIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    import hashlib
    from datetime import UTC, datetime

    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = await db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    if reset is None or reset.used or reset.expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Lien invalide ou expiré"
        )
    user = await db.get(User, reset.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Utilisateur introuvable"
        )
    user.password_hash = hash_password(payload.new_password)
    reset.used = True
    await db.flush()
    await audit.record(db, action="user.password.reset", actor_id=user.id, target=str(user.id))
    return {"detail": "Mot de passe réinitialisé."}
