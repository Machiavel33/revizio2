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
    AdminUserCreate,
    AdminUserOut,
    AdminUserRoleUpdate,
    AdminUserUpdate,
    AlertOut,
    AuditLogOut,
    AuditVerifyOut,
    EmailLogOut,
    OnlineOut,
    PlatformKeyCreate,
    PlatformKeyCreateFull,
    PlatformKeyOut,
    SmtpConfigIn,
    SmtpConfigOut,
    SystemInfoOut,
    TestEmailIn,
    UserUsageOut,
)
from app.services import audit, mail, presence, system_info
from app.services import usage as usage_svc

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


@router.get("/system", response_model=SystemInfoOut)
async def get_system_info(_admin: AdminUser) -> dict:
    """Versions, santé des services, uptime."""
    return await system_info.system_info()


@router.get("/online", response_model=OnlineOut)
async def get_online_users(_admin: AdminUser) -> OnlineOut:
    """Utilisateurs actuellement connectés (présence live via Redis)."""
    users = await presence.online_users()
    return OnlineOut(count=len(users), users=users)


# --- Alertes ---


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    unread_only: bool = False,
) -> list:
    from app.models import Alert

    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(200)
    if unread_only:
        stmt = stmt.where(Alert.is_read.is_(False))
    return list(await db.scalars(stmt))


@router.get("/alerts/count")
async def alerts_count(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.models import Alert

    total = int(
        await db.scalar(select(func.count()).select_from(Alert).where(Alert.is_read.is_(False)))
        or 0
    )
    return {"unread": total}


@router.post("/alerts/{alert_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_alert_read(
    alert_id: uuid.UUID,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    from app.models import Alert

    alert = await db.get(Alert, alert_id)
    if alert is not None:
        alert.is_read = True
        await db.flush()


# --- Usage / quotas par utilisateur ---


@router.get("/usage", response_model=list[UserUsageOut])
async def list_usage(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserUsageOut]:
    from app.core.config import settings

    users = (await db.scalars(select(User).order_by(User.created_at.desc()))).all()
    result = []
    for u in users:
        usage = await usage_svc.monthly_usage(db, u.id)
        flags = await usage_svc.detect_abuse(db, u, None)
        result.append(
            UserUsageOut(
                user_id=u.id,
                email=u.email,
                key_mode=u.key_mode,
                audio_minutes=usage["audio_minutes"],
                sheet_count=usage["sheet_count"],
                cost_usd=usage["cost_usd"],
                quota_audio_minutes=settings.quota_audio_minutes,
                quota_sheet_count=settings.quota_sheet_count,
                abuse_flags=flags,
            )
        )
    return result


# --- Création / gestion complète des utilisateurs ---


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserOut:
    from app.core.security import hash_password

    if payload.role not in ("student", "admin"):
        raise HTTPException(status_code=400, detail="Rôle invalide")
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email déjà utilisé")
    full_name = f"{payload.first_name} {payload.last_name}".strip()
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        display_name=payload.display_name or full_name or payload.email.split("@")[0],
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await audit.record(
        db,
        action="admin.user.create",
        actor_id=_admin.id,
        target=str(user.id),
        metadata={"email": user.email, "role": user.role},
    )
    mail.send_welcome(user.email, user.display_name)
    out = AdminUserOut.model_validate(user)
    out.course_count = 0
    out.byok_providers = []
    out.platform_providers = await _platform_providers(db)
    return out


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
async def set_user_role(
    user_id: uuid.UUID,
    payload: AdminUserRoleUpdate,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserOut:
    if payload.role not in ("student", "admin"):
        raise HTTPException(status_code=400, detail="Rôle invalide")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.role = payload.role
    await db.flush()
    await audit.record(
        db,
        action="admin.user.role",
        actor_id=_admin.id,
        target=str(user_id),
        metadata={"role": payload.role},
    )
    out = AdminUserOut.model_validate(user)
    out.course_count = 0
    out.byok_providers = []
    out.platform_providers = await _platform_providers(db)
    return out


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    if user_id == _admin.id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer son propre compte")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    await db.delete(user)
    await audit.record(db, action="admin.user.delete", actor_id=_admin.id, target=str(user_id))


@router.post("/users/{user_id}/force-reset", status_code=status.HTTP_200_OK)
async def force_password_reset(
    user_id: uuid.UUID,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Envoie un lien de réinitialisation à l'utilisateur (intervention admin)."""
    import hashlib
    import secrets
    from datetime import UTC, datetime, timedelta

    from app.models import PasswordResetToken

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    await db.flush()
    mail.send_password_reset(user.email, user.display_name, token)
    await audit.record(db, action="admin.user.force_reset", actor_id=_admin.id, target=str(user_id))
    return {"detail": "Lien de réinitialisation envoyé"}


# --- Clés plateforme avec compte associé ---


@router.post(
    "/platform-keys/full", response_model=PlatformKeyOut, status_code=status.HTTP_201_CREATED
)
async def create_platform_key_full(
    payload: PlatformKeyCreateFull,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PlatformKey:
    from app.core.crypto import encrypt_secret, mask_secret

    existing = await db.scalar(select(PlatformKey).where(PlatformKey.provider == payload.provider))
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Clé {payload.provider} existe déjà")
    key = PlatformKey(
        provider=payload.provider,
        account_label=payload.account_label,
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
        metadata={"provider": payload.provider, "account": payload.account_label},
    )
    return key


# --- Emails : config SMTP + logs + test ---


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    from app.models import SystemSetting

    row = await db.get(SystemSetting, key)
    return row.value if row else None


async def _set_setting(db: AsyncSession, key: str, value: str, is_secret: bool = False) -> None:
    from app.models import SystemSetting

    row = await db.get(SystemSetting, key)
    if row is None:
        db.add(SystemSetting(key=key, value=value, is_secret=is_secret))
    else:
        row.value = value
        row.is_secret = is_secret
    await db.flush()


@router.get("/email/config", response_model=SmtpConfigOut)
async def get_email_config(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SmtpConfigOut:
    from app.core.config import settings

    host = await _get_setting(db, "smtp_host") or settings.smtp_host
    port = await _get_setting(db, "smtp_port") or str(settings.smtp_port)
    user = await _get_setting(db, "smtp_user") or settings.smtp_user
    use_tls = await _get_setting(db, "smtp_use_tls")
    from_addr = await _get_setting(db, "smtp_from") or settings.smtp_from
    return SmtpConfigOut(
        host=host,
        port=int(port),
        user=user,
        use_tls=(use_tls != "false") if use_tls else settings.smtp_use_tls,
        from_addr=from_addr,
        configured=bool(host),
    )


@router.put("/email/config", response_model=SmtpConfigOut)
async def set_email_config(
    payload: SmtpConfigIn,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SmtpConfigOut:
    await _set_setting(db, "smtp_host", payload.host)
    await _set_setting(db, "smtp_port", str(payload.port))
    await _set_setting(db, "smtp_user", payload.user)
    if payload.password:
        await _set_setting(db, "smtp_password", payload.password, is_secret=True)
    await _set_setting(db, "smtp_use_tls", "true" if payload.use_tls else "false")
    await _set_setting(db, "smtp_from", payload.from_addr)
    # Met à jour le cache mémoire pour prise en compte immédiate
    mail.update_smtp_cache(
        {
            "host": payload.host,
            "port": payload.port,
            "user": payload.user,
            "password": payload.password,
            "use_tls": payload.use_tls,
            "from": payload.from_addr,
        }
    )
    await audit.record(db, action="admin.email.config", actor_id=_admin.id, target="smtp")
    return SmtpConfigOut(
        host=payload.host,
        port=payload.port,
        user=payload.user,
        use_tls=payload.use_tls,
        from_addr=payload.from_addr,
        configured=bool(payload.host),
    )


@router.post("/email/test", status_code=status.HTTP_200_OK)
async def test_email(
    payload: TestEmailIn,
    _admin: AdminUser,
) -> dict:
    ok = mail.send_test(payload.to)
    return {"sent": ok}


@router.get("/email/logs", response_model=list[EmailLogOut])
async def email_logs(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list:
    from app.models import EmailLog

    return list(await db.scalars(select(EmailLog).order_by(EmailLog.created_at.desc()).limit(200)))


# --- Suppression d'alerte ---


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    from app.models import Alert

    alert = await db.get(Alert, alert_id)
    if alert is not None:
        await db.delete(alert)


@router.get("/platform-keys/accounts")
async def platform_accounts(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    """Liste des comptes associés déjà utilisés (pour autocomplete)."""
    rows = await db.scalars(
        select(PlatformKey.account_label).where(PlatformKey.account_label != "").distinct()
    )
    return [r for r in rows if r]
