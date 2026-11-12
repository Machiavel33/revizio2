"""Modèles SQLAlchemy — Revizio."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    last_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    oauth_provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    oauth_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # 2FA TOTP (facultatif) : secret chiffré AES-256-GCM, backup codes hachés
    totp_secret: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    backup_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Mode de clé IA : "byok" (clé perso) ou "platform" (clé fournie par la plateforme)
    key_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="byok")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    api_keys: Mapped[list["UserApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    courses: Mapped[list["Course"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserApiKey(Base):
    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_hint: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="api_keys")


class PlatformKey(Base):
    """Clés API globales fournies par la plateforme (admin).

    Un utilisateur en mode "platform" utilise ces clés au lieu des siennes.
    Chiffrées AES-256-GCM, une par provider.
    """

    __tablename__ = "platform_keys"
    __table_args__ = (UniqueConstraint("provider", name="uq_platform_provider"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    # Compte associé à la clé (ex: "compte OpenAI de l'école", email du compte)
    account_label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_hint: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Cours sans titre")
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="fr")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="recording")
    audio_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped["User"] = relationship(back_populates="courses")
    transcript: Mapped["Transcript | None"] = relationship(
        back_populates="course", cascade="all, delete-orphan", uselist=False
    )
    study_sheet: Mapped["StudySheet | None"] = relationship(
        back_populates="course", cascade="all, delete-orphan", uselist=False
    )
    jobs: Mapped[list["Job"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), unique=True
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    segments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    course: Mapped["Course"] = relationship(back_populates="transcript")


class StudySheet(Base):
    __tablename__ = "study_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # course_id nullable : une fiche peut être créée manuellement (sans cours)
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), unique=True, nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    course: Mapped["Course | None"] = relationship(back_populates="study_sheet")
    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="study_sheet", cascade="all, delete-orphan"
    )


class Flashcard(Base):
    __tablename__ = "flashcards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    study_sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_sheets.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    study_sheet: Mapped["StudySheet"] = relationship(back_populates="flashcards")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped["Course"] = relationship(back_populates="jobs")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """Journal d'audit immuable (chaîne de hachage append-only).

    Chaque entrée contient le hash de l'entrée précédente (prev_hash) et son
    propre hash (entry_hash = SHA256(prev_hash || payload)). Toute altération
    d'une entrée casse la chaîne et est détectable via verify_chain().
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # Séquence monotone pour l'ordre strict de la chaîne
    seq: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    course_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    key_source: Mapped[str] = mapped_column(String(20), nullable=False)
    audio_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EmailLog(Base):
    """Historique des emails envoyés (traçabilité admin)."""

    __tablename__ = "email_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    to_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")  # sent|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class SystemSetting(Base):
    """Réglages système modifiables par l'admin (clé/valeur, secrets chiffrés)."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class ExamFolder(Base):
    """Dossier d'examen : regroupe des fiches/cours pour préparer un examen."""

    __tablename__ = "exam_folders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    items: Mapped[list["ExamFolderItem"]] = relationship(
        back_populates="folder", cascade="all, delete-orphan"
    )


class ExamFolderItem(Base):
    """Élément d'un dossier d'examen : une fiche de révision (par id)."""

    __tablename__ = "exam_folder_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    folder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_folders.id", ondelete="CASCADE"), index=True
    )
    study_sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_sheets.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    folder: Mapped["ExamFolder"] = relationship(back_populates="items")


class Quiz(Base):
    """Quiz généré par l'IA à partir de fiches de révision."""

    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_folders.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Quiz")
    model: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")
