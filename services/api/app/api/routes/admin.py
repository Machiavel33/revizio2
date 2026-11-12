"""Routes Admin : gestion utilisateurs, supervision jobs, statistiques."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.core.database import get_db
from app.models import AuditLog, Course, Job, User
from app.schemas.admin import (
    AdminJobOut,
    AdminStats,
    AdminUserOut,
    AdminUserUpdate,
    AuditLogOut,
    AuditVerifyOut,
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
    result = []
    for user, course_count in rows.all():
        out = AdminUserOut.model_validate(user)
        out.course_count = int(course_count)
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
    user.is_active = payload.is_active
    await db.flush()
    await audit.record(
        db,
        action="admin.user.update",
        actor_id=_admin.id,
        target=str(user_id),
        metadata={"is_active": payload.is_active},
    )
    course_count = int(
        await db.scalar(select(func.count()).select_from(Course).where(Course.user_id == user.id))
        or 0
    )
    out = AdminUserOut.model_validate(user)
    out.course_count = course_count
    return out


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
