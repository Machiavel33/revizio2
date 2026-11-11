"""Routes BYOK : gestion des clés API utilisateur (chiffrées)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.crypto import encrypt_secret, mask_secret
from app.core.database import get_db
from app.models import UserApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


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
    await db.delete(key)
