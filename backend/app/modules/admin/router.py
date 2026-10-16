"""Rotas de administração (role admin)."""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_admin
from app.core.errors import NotFoundError
from app.modules.admin.schemas import (
    AdminQuestionPage,
    AdminThemeOut,
    ThemeIn,
    ThemeUpdate,
)
from app.modules.essays.models import EssayTheme
from app.modules.questions import service as questions
from app.modules.questions.models import KnowledgeArea, Subject
from app.modules.questions.schemas import (
    AdminQuestionOut,
    AdminQuestionUpdate,
    QuestionListItem,
    SubjectRef,
)
from app.modules.users.models import User
from app.storage import LocalStorage, get_storage

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/questions", response_model=AdminQuestionPage)
async def review_queue(
    reviewed: bool | None = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Fila de revisão das questões importadas (`?reviewed=false`)."""
    rows, nxt, total = await questions.admin_list(session, reviewed, limit, cursor)
    areas = {a.id: a.code for a in await session.scalars(select(KnowledgeArea))}
    subjects = {s.id: s.name for s in await session.scalars(select(Subject))}
    items = [
        QuestionListItem(
            id=q.id,
            year=q.year,
            area_code=areas[q.area_id],
            subject=SubjectRef(id=q.subject_id, name=subjects[q.subject_id])
            if q.subject_id
            else None,
            skill_code=q.skill_code,
            foreign_language=q.foreign_language,
            difficulty=questions.difficulty_of(q.irt_b),
            preview=questions.preview(q.statement_md),
            bookmarked=False,
            last_attempt_correct=None,
        )
        for q in rows
    ]
    return AdminQuestionPage(items=items, next_cursor=nxt, total=total)


@router.get("/questions/{question_id}", response_model=AdminQuestionOut)
async def get_question(
    question_id: int,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    return await questions.admin_get(session, storage, admin, question_id)


@router.patch("/questions/{question_id}", response_model=AdminQuestionOut)
async def update_question(
    question_id: int,
    data: AdminQuestionUpdate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    await questions.admin_update(session, question_id, data)
    return await questions.admin_get(session, storage, admin, question_id)


def _theme_out(t: EssayTheme) -> AdminThemeOut:
    return AdminThemeOut(
        id=t.id,
        title=t.title,
        year=t.year,
        is_official=t.is_official,
        motivating_texts=t.motivating_texts,
    )


@router.get("/essay-themes", response_model=list[AdminThemeOut])
async def list_themes(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    rows = await session.scalars(
        select(EssayTheme).order_by(EssayTheme.year.desc().nulls_last(), EssayTheme.title)
    )
    return [_theme_out(t) for t in rows]


@router.post("/essay-themes", response_model=AdminThemeOut, status_code=status.HTTP_201_CREATED)
async def create_theme(
    data: ThemeIn,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    theme = EssayTheme(**data.model_dump(), created_by=admin.id)
    session.add(theme)
    await session.commit()
    await session.refresh(theme)
    return _theme_out(theme)


@router.patch("/essay-themes/{theme_id}", response_model=AdminThemeOut)
async def update_theme(
    theme_id: uuid.UUID,
    data: ThemeUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    theme = await session.get(EssayTheme, theme_id)
    if theme is None:
        raise NotFoundError("Tema não encontrado.")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ("title", "is_official") and value is None:
            continue
        setattr(theme, key, value)
    await session.commit()
    await session.refresh(theme)
    return _theme_out(theme)
