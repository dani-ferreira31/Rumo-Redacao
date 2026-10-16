import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.modules.questions import service
from app.modules.questions.schemas import (
    AnswerIn,
    AnswerOut,
    AreaOut,
    PracticeSessionIn,
    PracticeSessionOut,
    QuestionFilters,
    QuestionListQuery,
    QuestionOut,
    QuestionPage,
    QuestionStatsOut,
    SessionResult,
)
from app.modules.users.models import User
from app.storage import LocalStorage, get_storage

router = APIRouter(tags=["questions"])


@router.get("/catalog/areas", response_model=list[AreaOut])
async def catalog(
    _: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Áreas com disciplinas e tópicos (árvore)."""
    return await service.catalog(session)


@router.get("/questions", response_model=QuestionPage)
async def list_questions(
    query: Annotated[QuestionListQuery, Query()],
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Lista SEM gabarito."""
    filters = QuestionFilters(**query.model_dump(exclude={"limit", "cursor"}))
    return await service.list_questions(session, user, filters, query.limit, query.cursor)


@router.get("/questions/stats", response_model=QuestionStatsOut)
async def question_stats(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await service.stats(session, user)


@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Enunciado, alternativas e imagens, SEM gabarito."""
    return await service.get_question(session, storage, user, question_id)


@router.post("/questions/{question_id}/answer", response_model=AnswerOut)
async def answer(
    question_id: int,
    data: AnswerIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Registra a resposta. Em sessão de lista/simulado, o gabarito só sai no final."""
    return await service.answer(session, user, question_id, data)


@router.put("/questions/{question_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT)
async def bookmark(
    question_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.set_bookmark(session, user, question_id, True)


@router.delete("/questions/{question_id}/bookmark", status_code=status.HTTP_204_NO_CONTENT)
async def unbookmark(
    question_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.set_bookmark(session, user, question_id, False)


@router.post(
    "/practice-sessions", response_model=PracticeSessionOut, status_code=status.HTTP_201_CREATED
)
async def create_session(
    data: PracticeSessionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.create_session(session, user, data)


@router.get("/practice-sessions/{session_id}", response_model=PracticeSessionOut)
async def get_session_(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.get_session(session, user, session_id)


@router.post("/practice-sessions/{session_id}/finish", response_model=SessionResult)
async def finish_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Encerra a sessão e devolve gabarito e acerto por área."""
    return await service.finish_session(session, user, session_id)
