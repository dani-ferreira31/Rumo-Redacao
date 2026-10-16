import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user, require_feature
from app.modules.planner import service
from app.modules.planner.schemas import (
    BlockIn,
    BlockOut,
    BlockUpdate,
    PlanIn,
    PlanListItem,
    PlanOut,
    PlanSummary,
    PlanUpdate,
)
from app.modules.users.models import User

router = APIRouter(
    prefix="/study-plans",
    tags=["study-plans"],
    dependencies=[Depends(require_feature("planner"))],
)


@router.get("", response_model=list[PlanListItem])
async def list_plans(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await service.list_plans(session, user)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    data: PlanIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """O primeiro cronograma do aluno já nasce ativo."""
    return await service.plan_out(session, await service.create_plan(session, user, data))


@router.get("/active", response_model=PlanOut)
async def active_plan(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await service.plan_out(session, await service.get_active(session, user))


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.plan_out(session, await service.get_plan(session, user, plan_id))


@router.patch("/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: uuid.UUID,
    data: PlanUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.plan_out(session, await service.update_plan(session, user, plan_id, data))


@router.post("/{plan_id}/activate", response_model=PlanOut)
async def activate(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Torna este o cronograma ativo (desativa os outros na mesma transação)."""
    return await service.plan_out(session, await service.activate(session, user, plan_id))


@router.post("/{plan_id}/duplicate", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def duplicate(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.plan_out(session, await service.duplicate(session, user, plan_id))


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_plan(session, user, plan_id)


@router.post("/{plan_id}/blocks", response_model=BlockOut, status_code=status.HTTP_201_CREATED)
async def create_block(
    plan_id: uuid.UUID,
    data: BlockIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """409 `block_overlap` (com o bloco conflitante em `details.conflict`) se sobrepuser."""
    block = await service.create_block(session, user, plan_id, data)
    return await service.block_out(session, block)


@router.patch("/{plan_id}/blocks/{block_id}", response_model=BlockOut)
async def update_block(
    plan_id: uuid.UUID,
    block_id: uuid.UUID,
    data: BlockUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Mesmas validações da criação (usado ao arrastar e redimensionar)."""
    block = await service.update_block(session, user, plan_id, block_id, data)
    return await service.block_out(session, block)


@router.delete("/{plan_id}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    plan_id: uuid.UUID,
    block_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_block(session, user, plan_id, block_id)


@router.get("/{plan_id}/summary", response_model=PlanSummary)
async def summary(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Horas por semana, por área e por dia."""
    return await service.summary(session, user, plan_id)
