"""Schémas Pydantic — Admin."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    key_mode: str = "byok"
    created_at: datetime
    course_count: int = 0
    # Providers pour lesquels l'utilisateur a une clé perso (BYOK)
    byok_providers: list[str] = []
    # Providers pour lesquels une clé plateforme existe (utilisable en mode platform)
    platform_providers: list[str] = []


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    key_mode: str | None = None


class PlatformKeyCreate(BaseModel):
    provider: str
    api_key: str


class PlatformKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    key_hint: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    total_courses: int
    ready_courses: int
    failed_courses: int
    total_jobs: int
    queued_jobs: int
    running_jobs: int
    failed_jobs: int


class AdminJobOut(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    type: str
    status: str
    error: str | None
    created_at: datetime
    finished_at: datetime | None
    user_email: str
    course_title: str


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    actor_id: uuid.UUID | None
    action: str
    target: str | None
    metadata_: dict = {}
    prev_hash: str
    entry_hash: str
    created_at: datetime


class AuditVerifyOut(BaseModel):
    ok: bool
    broken_at_seq: int | None
    total_entries: int


class ServiceStatus(BaseModel):
    name: str
    status: str
    error: str | None = None
    workers: list[str] = []


class AppInfo(BaseModel):
    name: str
    version: str
    environment: str
    python: str
    platform: str
    uptime_seconds: int


class SystemInfoOut(BaseModel):
    app: AppInfo
    services: list[ServiceStatus]
    storage_backend: str
    rate_limit: dict


class OnlineUser(BaseModel):
    user_id: str
    email: str
    display_name: str
    last_seen: int
    idle_seconds: int


class OnlineOut(BaseModel):
    count: int
    users: list[OnlineUser]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: str
    category: str
    title: str
    message: str
    user_id: uuid.UUID | None
    metadata_: dict = {}
    is_read: bool
    created_at: datetime


class UserUsageOut(BaseModel):
    user_id: uuid.UUID
    email: str
    key_mode: str
    audio_minutes: float
    sheet_count: int
    cost_usd: float
    quota_audio_minutes: int
    quota_sheet_count: int
    abuse_flags: list[str] = []
