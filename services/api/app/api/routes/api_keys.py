"""Routes BYOK : gestion des clés API utilisateur (chiffrées)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.crypto import encrypt_secret, mask_secret
from app.core.database import get_db
from app.models import PlatformKey, UserApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyOut, KeyModeOut, KeyModeUpdate
from app.services import audit

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.get("/key-mode", response_model=KeyModeOut)
async def get_key_mode(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KeyModeOut:
    platform = list(
        await db.scalars(select(PlatformKey.provider).where(PlatformKey.is_active.is_(True)))
    )
    return KeyModeOut(key_mode=user.key_mode, platform_available=platform)


@router.put("/key-mode", response_model=KeyModeOut)
async def set_key_mode(
    payload: KeyModeUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KeyModeOut:
    if payload.key_mode not in ("byok", "platform"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="key_mode doit être 'byok' ou 'platform'",
        )
    platform = list(
        await db.scalars(select(PlatformKey.provider).where(PlatformKey.is_active.is_(True)))
    )
    if payload.key_mode == "platform" and not platform:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune clé plateforme disponible",
        )
    user.key_mode = payload.key_mode
    await db.flush()
    await audit.record(
        db,
        action="user.key_mode.update",
        actor_id=user.id,
        target=str(user.id),
        metadata={"key_mode": payload.key_mode},
    )
    return KeyModeOut(key_mode=user.key_mode, platform_available=platform)


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserApiKey]:
    result = await db.scalars(
        select(UserApiKey).where(UserApiKey.user_id == user.id).order_by(UserApiKey.created_at)
    )
    return list(result)


@router.post("", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: ApiKeyCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserApiKey:
    existing = await db.scalar(
        select(UserApiKey).where(
            UserApiKey.user_id == user.id,
            UserApiKey.provider == payload.provider,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Une clé {payload.provider} existe déjà. Supprimez-la d'abord.",
        )

    if payload.is_default:
        await db.execute(
            update(UserApiKey).where(UserApiKey.user_id == user.id).values(is_default=False)
        )

    key = UserApiKey(
        user_id=user.id,
        provider=payload.provider,
        encrypted_key=encrypt_secret(payload.api_key),
        key_hint=mask_secret(payload.api_key),
        is_default=payload.is_default,
    )
    db.add(key)
    await db.flush()
    await audit.record(
        db,
        action="byok.create",
        actor_id=user.id,
        target=str(key.id),
        metadata={"provider": payload.provider},
    )
    return key


@router.post("/{key_id}/rotate", response_model=ApiKeyOut)
async def rotate_key(
    key_id: uuid.UUID,
    payload: ApiKeyCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserApiKey:
    """Remplace la valeur d'une clé API existante (rotation côté utilisateur)."""
    key = await db.get(UserApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clé introuvable",
        )
    if payload.provider != key.provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le provider doit correspondre à la clé existante",
        )
    key.encrypted_key = encrypt_secret(payload.api_key)
    key.key_hint = mask_secret(payload.api_key)
    await db.flush()
    await audit.record(
        db,
        action="byok.rotate",
        actor_id=user.id,
        target=str(key.id),
        metadata={"provider": key.provider},
    )
    return key


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    key = await db.get(UserApiKey, key_id)
    if key is None or key.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clé introuvable",
        )
    provider = key.provider
    await db.delete(key)
    await audit.record(
        db,
        action="byok.delete",
        actor_id=user.id,
        target=str(key_id),
        metadata={"provider": provider},
    )
