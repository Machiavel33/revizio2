"""Exposition des modèles pour Alembic et l'app."""

from app.models.models import (
    Alert,
    AuditLog,
    Course,
    EmailLog,
    Flashcard,
    Job,
    PasswordResetToken,
    PlatformKey,
    StudySheet,
    SystemSetting,
    Transcript,
    UsageLog,
    UsageRecord,
    User,
    UserApiKey,
)

__all__ = [
    "User",
    "UserApiKey",
    "PlatformKey",
    "Course",
    "Transcript",
    "StudySheet",
    "Flashcard",
    "Job",
    "UsageLog",
    "UsageRecord",
    "AuditLog",
    "Alert",
    "PasswordResetToken",
    "EmailLog",
    "SystemSetting",
]
