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
    created_at: datetime
    course_count: int = 0


class AdminUserUpdate(BaseModel):
    is_active: bool


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
