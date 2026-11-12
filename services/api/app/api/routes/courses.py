"""Routes Courses : CRUD, upload audio, déclenchement des jobs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.models import Course, Job
from app.schemas.course import (
    CourseCreate,
    CourseDetail,
    CourseOut,
    CourseUpdate,
    JobOut,
)
from app.services.storage import build_audio_key, upload_audio

router = APIRouter(prefix="/courses", tags=["courses"])


async def _get_owned_course(course_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> Course:
    course = await db.scalar(
        select(Course)
        .where(Course.id == course_id, Course.user_id == user_id)
        .options(
            selectinload(Course.transcript),
            selectinload(Course.study_sheet),
            selectinload(Course.jobs),
        )
    )
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cours introuvable")
    return course


@router.get("", response_model=list[CourseOut])
async def list_courses(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Course]:
    result = await db.scalars(
        select(Course).where(Course.user_id == user.id).order_by(Course.created_at.desc())
    )
    return list(result)


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
async def create_course(
    payload: CourseCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Course:
    course = Course(
        user_id=user.id,
        title=payload.title,
        subject=payload.subject,
        tags=payload.tags,
        language=payload.language,
        status="recording",
    )
    db.add(course)
    await db.flush()
    return course


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Course:
    return await _get_owned_course(course_id, user.id, db)


@router.patch("/{course_id}", response_model=CourseOut)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Course:
    course = await _get_owned_course(course_id, user.id, db)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(course, field, value)
    await db.flush()
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    course = await _get_owned_course(course_id, user.id, db)
    await db.delete(course)


@router.post("/{course_id}/audio", response_model=CourseOut)
async def upload_course_audio(
    course_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> Course:
    course = await _get_owned_course(course_id, user.id, db)

    # Validation du type MIME (whitelist)
    content_type = (file.content_type or "").lower()
    if content_type not in settings.allowed_audio_type_list:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Type de fichier non supporté: {content_type or 'inconnu'}",
        )

    # Lecture bornée : refuse les fichiers trop volumineux (prévention DoS mémoire)
    max_bytes = settings.max_upload_bytes
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Fichier trop volumineux (max {max_bytes // (1024 * 1024)} Mo)",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fichier vide")

    key = build_audio_key(user.id, course.id, file.filename or "audio.webm")
    url = upload_audio(key, data, content_type=content_type)
    course.audio_url = url
    course.status = "transcribing"
    await db.flush()
    return course


@router.post(
    "/{course_id}/process", response_model=list[JobOut], status_code=status.HTTP_202_ACCEPTED
)
async def process_course(
    course_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Job]:
    """Déclenche la transcription batch puis la génération de fiche (jobs async)."""
    course = await _get_owned_course(course_id, user.id, db)
    if not course.audio_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun audio uploadé pour ce cours",
        )

    transcribe_job = Job(course_id=course.id, type="transcribe", status="queued")
    sheet_job = Job(course_id=course.id, type="generate_sheet", status="queued")
    db.add_all([transcribe_job, sheet_job])
    course.status = "transcribing"
    await db.flush()

    # Import tardif pour éviter la dépendance circulaire Celery <-> app
    from app.workers.tasks import generate_sheet_task, transcribe_task

    transcribe_task.delay(str(course.id), str(transcribe_job.id))
    generate_sheet_task.delay(str(course.id), str(sheet_job.id))

    return [transcribe_job, sheet_job]
