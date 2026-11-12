"""Routes Admin : gestion utilisateurs, supervision jobs, statistiques."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.core.crypto import encrypt_secret, mask_secret
from app.core.database import get_db
from app.models import AuditLog, Course, Job, PlatformKey, User, UserApiKey
from app.schemas.admin import (
    AdminJobOut,
    AdminStats,
    AdminUserOut,
    AdminUserUpdate,
    AuditLogOut,
    AuditVerifyOut,
    PlatformKeyCreate,
    PlatformKeyOut,
)
from app.services import audit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
async def stats(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminStats:
    async def count(model, *where) -> int:
        stmt = select(func.count()).select_from(model)
        for w in where:
            stmt = stmt.where(w)
        return int(await db.scalar(stmt) or 0)

    return AdminStats(
        total_users=await count(User),
        active_users=await count(User, User.is_active.is_(True)),
        total_courses=await count(Course),
        ready_courses=await count(Course, Course.status == "ready"),
        failed_courses=await count(Course, Course.status == "failed"),
        total_jobs=await count(Job),
        queued_jobs=await count(Job, Job.status == "queued"),
        running_jobs=await count(Job, Job.status == "running"),
        failed_jobs=await count(Job, Job.status == "failed"),
    )


async def _platform_providers(db: AsyncSession) -> list[str]:
    rows = await db.scalars(select(PlatformKey.provider).where(PlatformKey.is_active.is_(True)))
    return list(rows)


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminUserOut]:
    rows = await db.execute(
        select(User, func.count(Course.id))
        .outerjoin(Course, Course.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    platform = await _platform_providers(db)
    # Providers BYOK par utilisateur
    byok_rows = await db.execute(select(UserApiKey.user_id, UserApiKey.provider))
    byok_map: dict[uuid.UUID, list[str]] = {}
    for uid, provider in byok_rows.all():
        byok_map.setdefault(uid, []).append(provider)

    result = []
    for user, course_count in rows.all():
        out = AdminUserOut.model_validate(user)
        out.course_count = int(course_count)
        out.byok_providers = sorted(byok_map.get(user.id, []))
        out.platform_providers = platform
        result.append(out)
    return result


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    changes: dict = {}
    if payload.is_active is not None:
        user.is_active = payload.is_active
        changes["is_active"] = payload.is_active
    if payload.key_mode is not None:
        if payload.key_mode not in ("byok", "platform"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="key_mode doit être 'byok' ou 'platform'",
            )
        user.key_mode = payload.key_mode
        changes["key_mode"] = payload.key_mode
    await db.flush()
    await audit.record(
        db,
        action="admin.user.update",
        actor_id=_admin.id,
        target=str(user_id),
        metadata=changes,
    )
    course_count = int(
        await db.scalar(select(func.count()).select_from(Course).where(Course.user_id == user.id))
        or 0
    )
    byok = list(await db.scalars(select(UserApiKey.provider).where(UserApiKey.user_id == user.id)))
    out = AdminUserOut.model_validate(user)
    out.course_count = course_count
    out.byok_providers = sorted(byok)
    out.platform_providers = await _platform_providers(db)
    return out


# --- Clés plateforme (globales) ---


@router.get("/platform-keys", response_model=list[PlatformKeyOut])
async def list_platform_keys(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PlatformKey]:
    return list(await db.scalars(select(PlatformKey).order_by(PlatformKey.provider)))


@router.post("/platform-keys", response_model=PlatformKeyOut, status_code=status.HTTP_201_CREATED)
async def create_platform_key(
    payload: PlatformKeyCreate,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformKey:
    existing = await db.scalar(select(PlatformKey).where(PlatformKey.provider == payload.provider))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Une clé plateforme {payload.provider} existe déjà",
        )
    key = PlatformKey(
        provider=payload.provider,
        encrypted_key=encrypt_secret(payload.api_key),
        key_hint=mask_secret(payload.api_key),
        is_active=True,
    )
    db.add(key)
    await db.flush()
    await audit.record(
        db,
        action="admin.platform_key.create",
        actor_id=_admin.id,
        target=str(key.id),
        metadata={"provider": payload.provider},
    )
    return key


@router.delete("/platform-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_platform_key(
    key_id: uuid.UUID,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    key = await db.get(PlatformKey, key_id)
    if key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clé introuvable")
    provider = key.provider
    await db.delete(key)
    await audit.record(
        db,
        action="admin.platform_key.delete",
        actor_id=_admin.id,
        target=str(key_id),
        metadata={"provider": provider},
    )


@router.get("/jobs", response_model=list[AdminJobOut])
async def list_jobs(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdminJobOut]:
    rows = await db.execute(
        select(Job, User.email, Course.title)
        .join(Course, Course.id == Job.course_id)
        .join(User, User.id == Course.user_id)
        .order_by(Job.created_at.desc())
        .limit(200)
    )
    return [
        AdminJobOut(
            id=job.id,
            course_id=job.course_id,
            type=job.type,
            status=job.status,
            error=job.error,
            created_at=job.created_at,
            finished_at=job.finished_at,
            user_email=email,
            course_title=title,
        )
        for job, email, title in rows.all()
    ]


@router.get("/audit", response_model=list[AuditLogOut])
async def list_audit(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
) -> list[AuditLog]:
    result = await db.scalars(select(AuditLog).order_by(AuditLog.seq.desc()).limit(min(limit, 500)))
    return list(result)


@router.get("/audit/verify", response_model=AuditVerifyOut)
async def verify_audit(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuditVerifyOut:
    ok, broken_at = await audit.verify_chain(db)
    total = int(await db.scalar(select(func.count()).select_from(AuditLog)) or 0)
    return AuditVerifyOut(ok=ok, broken_at_seq=broken_at, total_entries=total)
