"""Routes Révision : fiches manuelles, dossiers d'examen, quiz IA."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models import (
    ExamFolder,
    ExamFolderItem,
    Quiz,
    QuizQuestion,
    StudySheet,
)
from app.schemas.revision import (
    FolderCreate,
    FolderItemAdd,
    FolderOut,
    ManualSheetCreate,
    ManualSheetUpdate,
    QuizGenerateIn,
    QuizOut,
    SheetOut,
)
from app.services import quiz_generator
from app.workers.tasks import _resolve_key

router = APIRouter(prefix="/revision", tags=["revision"])


# --- Fiches manuelles ---


@router.get("/sheets", response_model=list[SheetOut])
async def list_sheets(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StudySheet]:
    """Toutes les fiches de l'utilisateur (manuelles + issues de cours)."""
    rows = await db.scalars(
        select(StudySheet)
        .where(StudySheet.user_id == user.id)
        .order_by(StudySheet.created_at.desc())
    )
    return list(rows)


@router.post("/sheets", response_model=SheetOut, status_code=status.HTTP_201_CREATED)
async def create_manual_sheet(
    payload: ManualSheetCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudySheet:
    sheet = StudySheet(
        user_id=user.id,
        course_id=None,
        title=payload.title,
        subject=payload.subject,
        tags=payload.tags,
        is_manual=True,
        content=payload.content,
        model="manual",
    )
    db.add(sheet)
    await db.flush()
    return sheet


@router.patch("/sheets/{sheet_id}", response_model=SheetOut)
async def update_manual_sheet(
    sheet_id: uuid.UUID,
    payload: ManualSheetUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StudySheet:
    sheet = await db.get(StudySheet, sheet_id)
    if sheet is None or sheet.user_id != user.id:
        raise HTTPException(status_code=404, detail="Fiche introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(sheet, k, v)
    await db.flush()
    return sheet


@router.delete("/sheets/{sheet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sheet(
    sheet_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    sheet = await db.get(StudySheet, sheet_id)
    if sheet is None or sheet.user_id != user.id:
        raise HTTPException(status_code=404, detail="Fiche introuvable")
    await db.delete(sheet)


# --- Dossiers d'examen ---


@router.get("/folders", response_model=list[FolderOut])
async def list_folders(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[FolderOut]:
    rows = await db.execute(
        select(ExamFolder, func.count(ExamFolderItem.id))
        .outerjoin(ExamFolderItem, ExamFolderItem.folder_id == ExamFolder.id)
        .where(ExamFolder.user_id == user.id)
        .group_by(ExamFolder.id)
        .order_by(ExamFolder.created_at.desc())
    )
    result = []
    for folder, count in rows.all():
        out = FolderOut.model_validate(folder)
        out.item_count = int(count)
        result.append(out)
    return result


@router.post("/folders", response_model=FolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: FolderCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FolderOut:
    folder = ExamFolder(
        user_id=user.id,
        name=payload.name,
        exam_date=payload.exam_date,
        description=payload.description,
    )
    db.add(folder)
    await db.flush()
    out = FolderOut.model_validate(folder)
    out.item_count = 0
    return out


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    folder = await db.get(ExamFolder, folder_id)
    if folder is None or folder.user_id != user.id:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    await db.delete(folder)


@router.post("/folders/{folder_id}/items", status_code=status.HTTP_201_CREATED)
async def add_folder_item(
    folder_id: uuid.UUID,
    payload: FolderItemAdd,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    folder = await db.get(ExamFolder, folder_id)
    if folder is None or folder.user_id != user.id:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    sheet = await db.get(StudySheet, payload.study_sheet_id)
    if sheet is None or sheet.user_id != user.id:
        raise HTTPException(status_code=404, detail="Fiche introuvable")
    existing = await db.scalar(
        select(ExamFolderItem).where(
            ExamFolderItem.folder_id == folder_id,
            ExamFolderItem.study_sheet_id == payload.study_sheet_id,
        )
    )
    if existing is None:
        db.add(ExamFolderItem(folder_id=folder_id, study_sheet_id=payload.study_sheet_id))
        await db.flush()
    return {"detail": "Fiche ajoutée au dossier"}


@router.get("/folders/{folder_id}/sheets", response_model=list[SheetOut])
async def folder_sheets(
    folder_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[StudySheet]:
    folder = await db.get(ExamFolder, folder_id)
    if folder is None or folder.user_id != user.id:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    rows = await db.scalars(
        select(StudySheet)
        .join(ExamFolderItem, ExamFolderItem.study_sheet_id == StudySheet.id)
        .where(ExamFolderItem.folder_id == folder_id)
    )
    return list(rows)


# --- Quiz IA ---


def _sheet_to_text(sheet: StudySheet) -> str:
    c = sheet.content or {}
    parts = [f"# {sheet.title or c.get('title', 'Fiche')}"]
    if c.get("summary"):
        parts.append(f"Résumé: {c['summary']}")
    for k in c.get("key_concepts", []):
        parts.append(f"- {k.get('term')}: {k.get('definition')}")
    for s in c.get("sections", []):
        parts.append(f"## {s.get('heading')}")
        parts.extend(f"- {p}" for p in s.get("points", []))
    for f in c.get("flashcards", []):
        parts.append(f"Q: {f.get('question')} R: {f.get('answer')}")
    return "\n".join(parts)


@router.post("/quiz/generate", response_model=QuizOut, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    payload: QuizGenerateIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuizOut:
    # Rassemble les fiches (dossier ou liste explicite)
    sheet_ids = list(payload.sheet_ids)
    if payload.folder_id is not None:
        folder = await db.get(ExamFolder, payload.folder_id)
        if folder is None or folder.user_id != user.id:
            raise HTTPException(status_code=404, detail="Dossier introuvable")
        rows = await db.scalars(
            select(StudySheet)
            .join(ExamFolderItem, ExamFolderItem.study_sheet_id == StudySheet.id)
            .where(ExamFolderItem.folder_id == payload.folder_id)
        )
        sheet_ids.extend([s.id for s in rows])

    if not sheet_ids:
        raise HTTPException(status_code=400, detail="Aucune fiche sélectionnée")

    sheets = []
    for sid in set(sheet_ids):
        s = await db.get(StudySheet, sid)
        if s is not None and s.user_id == user.id:
            sheets.append(s)
    if not sheets:
        raise HTTPException(status_code=400, detail="Fiches introuvables")

    text = "\n\n".join(_sheet_to_text(s) for s in sheets)

    # Résolution de la clé IA (platform/byok)
    provider = "anthropic"
    api_key, _src = await _resolve_key(db, user.id, "anthropic")
    if api_key is None:
        provider = "openai"
        api_key, _src = await _resolve_key(db, user.id, "openai")
    if api_key is None:
        raise HTTPException(status_code=400, detail="Aucune clé IA configurée")

    result = await quiz_generator.generate_quiz(
        text, provider=provider, api_key=api_key, count=payload.count
    )
    content = result["content"]

    quiz = Quiz(
        user_id=user.id,
        folder_id=payload.folder_id,
        title=content.get("title", "Quiz de révision"),
        model=result["model"],
    )
    db.add(quiz)
    await db.flush()
    for i, q in enumerate(content.get("questions", [])):
        db.add(
            QuizQuestion(
                quiz_id=quiz.id,
                position=i,
                question=q.get("question", ""),
                choices=q.get("choices", []),
                correct_index=int(q.get("correct_index", 0)),
                explanation=q.get("explanation", ""),
            )
        )
    await db.flush()
    await db.refresh(quiz, ["questions"])
    return QuizOut.model_validate(quiz)


@router.get("/quizzes", response_model=list[QuizOut])
async def list_quizzes(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Quiz]:
    rows = await db.scalars(
        select(Quiz).where(Quiz.user_id == user.id).order_by(Quiz.created_at.desc())
    )
    return list(rows)


@router.get("/quizzes/{quiz_id}", response_model=QuizOut)
async def get_quiz(
    quiz_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Quiz:
    quiz = await db.get(Quiz, quiz_id)
    if quiz is None or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz introuvable")
    await db.refresh(quiz, ["questions"])
    return quiz


@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    quiz = await db.get(Quiz, quiz_id)
    if quiz is None or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz introuvable")
    await db.delete(quiz)
