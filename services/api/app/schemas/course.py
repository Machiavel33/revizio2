"""Schémas Pydantic — Courses, Transcripts, StudySheets, Jobs."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CourseStatus = Literal["recording", "transcribing", "generating", "ready", "failed"]


class CourseCreate(BaseModel):
    title: str = Field(default="Cours sans titre", max_length=255)
    subject: str | None = Field(default=None, max_length=120)
    tags: list[str] = []
    language: str = Field(default="fr", max_length=10)


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    subject: str | None = Field(default=None, max_length=120)
    tags: list[str] | None = None
    status: CourseStatus | None = None
    duration_sec: int | None = Field(default=None, ge=0)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subject: str | None
    tags: list[str] = []
    language: str
    status: str
    audio_url: str | None
    duration_sec: int
    created_at: datetime
    updated_at: datetime


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    full_text: str
    segments: list[Any]
    provider: str
    model: str
    created_at: datetime


class StudySheetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    content: dict[str, Any]
    model: str
    version: int
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    type: str
    status: str
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class CourseDetail(CourseOut):
    transcript: TranscriptOut | None = None
    study_sheet: StudySheetOut | None = None
    jobs: list[JobOut] = []
