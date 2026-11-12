"""Routes 2FA TOTP (facultatif, opt-in).

- /2fa/setup : génère un secret + URI (non activé tant que non confirmé)
- /2fa/enable : confirme avec un code, active, retourne les backup codes
- /2fa/disable : désactive (code TOTP ou backup code requis)
- /2fa/status : état d'activation
- /2fa/verify : vérifie le challenge après login (mfa_token + code)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models import User
from app.schemas.auth import TokenPair
from app.schemas.totp import (
    TotpDisableIn,
    TotpEnableIn,
    TotpEnableOut,
    TotpSetupOut,
    TotpStatusOut,
    TotpVerifyIn,
)
from app.services import audit, totp

router = APIRouter(prefix="/2fa", tags=["2fa"])


@router.get("/status", response_model=TotpStatusOut)
async def status_2fa(user: CurrentUser) -> TotpStatusOut:
    return TotpStatusOut(enabled=user.totp_enabled)


@router.post("/setup", response_model=TotpSetupOut)
async def setup_2fa(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TotpSetupOut:
    if user.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA déjà activée. Désactivez-la d'abord.",
        )
    secret = totp.generate_secret()
    user.totp_secret = totp.encrypt_totp_secret(secret)
    await db.flush()
    return TotpSetupOut(
        secret=secret,
        provisioning_uri=totp.provisioning_uri(secret, user.email),
    )


@router.post("/enable", response_model=TotpEnableOut)
async def enable_2fa(
    payload: TotpEnableIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TotpEnableOut:
    if user.totp_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="2FA déjà activée")
    if user.totp_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun secret en attente. Lancez /2fa/setup d'abord.",
        )
    secret = totp.decrypt_totp_secret(user.totp_secret)
    if not totp.verify_code(secret, payload.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code TOTP invalide")
    plain_codes, hashed_codes = totp.generate_backup_codes()
    user.totp_enabled = True
    user.backup_codes = hashed_codes
    await db.flush()
    await audit.record(db, action="user.2fa.enable", actor_id=user.id, target=str(user.id))
    return TotpEnableOut(enabled=True, backup_codes=plain_codes)


@router.post("/disable", response_model=TotpStatusOut)
async def disable_2fa(
    payload: TotpDisableIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TotpStatusOut:
    if not user.totp_enabled or user.totp_secret is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA non activée")
    secret = totp.decrypt_totp_secret(user.totp_secret)
    valid = totp.verify_code(secret, payload.code)
    if not valid:
        idx = totp.verify_backup_code(payload.code, user.backup_codes)
        valid = idx is not None
    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code invalide")
    user.totp_enabled = False
    user.totp_secret = None
    user.backup_codes = []
    await db.flush()
    await audit.record(db, action="user.2fa.disable", actor_id=user.id, target=str(user.id))
    return TotpStatusOut(enabled=False)


@router.post("/verify", response_model=TokenPair)
async def verify_2fa(
    payload: TotpVerifyIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    """Vérifie le challenge 2FA après login et émet les tokens finaux."""
    try:
        data = decode_token(payload.mfa_token, expected_type="mfa")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token MFA invalide ou expiré"
        ) from exc

    import uuid as _uuid

    try:
        user_id = _uuid.UUID(data["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token MFA invalide"
        ) from exc
    user = await db.get(User, user_id)
    if user is None or not user.is_active or not user.totp_enabled or user.totp_secret is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="2FA indisponible")

    secret = totp.decrypt_totp_secret(user.totp_secret)
    valid = totp.verify_code(secret, payload.code)
    if not valid:
        # Tente un backup code (consommé si valide)
        idx = totp.verify_backup_code(payload.code, user.backup_codes)
        if idx is not None:
            codes = list(user.backup_codes)
            codes.pop(idx)
            user.backup_codes = codes
            await db.flush()
            valid = True
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code 2FA invalide")

    await audit.record(db, action="user.login.2fa", actor_id=user.id, target=str(user.id))
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
