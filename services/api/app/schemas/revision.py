"""Schémas Pydantic — Révision (fiches manuelles, dossiers, quiz)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --- Fiche manuelle ---
class ManualSheetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject: str | None = None
    tags: list[str] = []
    content: dict[str, Any] = {}


class ManualSheetUpdate(BaseModel):
    title: str | None = None
    subject: str | None = None
    tags: list[str] | None = None
    content: dict[str, Any] | None = None


class SheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID | None
    title: str
    subject: str | None
    tags: list[str]
    is_manual: bool
    content: dict[str, Any]
    created_at: datetime


# --- Dossiers d'examen ---
class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    exam_date: datetime | None = None
    description: str = ""


class FolderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    exam_date: datetime | None
    description: str
    created_at: datetime
    item_count: int = 0


class FolderItemAdd(BaseModel):
    study_sheet_id: uuid.UUID


# --- Quiz ---
class QuizGenerateIn(BaseModel):
    folder_id: uuid.UUID | None = None
    sheet_ids: list[uuid.UUID] = []
    count: int = Field(default=10, ge=1, le=30)


class QuizQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    question: str
    choices: list[str]
    correct_index: int
    explanation: str


class QuizOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    model: str
    created_at: datetime
    questions: list[QuizQuestionOut] = []
