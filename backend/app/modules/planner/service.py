"""Cronograma: planos (um ativo por usuário), blocos sem sobreposição e resumo."""

import uuid
from collections import defaultdict
from datetime import date, datetime, time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.modules.planner.models import StudyBlock, StudyPlan
from app.modules.planner.schemas import (
    HEX_RE,
    BlockIn,
    BlockOut,
    BlockUpdate,
    HoursBy,
    PlanIn,
    PlanListItem,
    PlanOut,
    PlanSummary,
    PlanUpdate,
)
from app.modules.questions.models import KnowledgeArea, Subject
from app.modules.users.models import User

WEEKDAY_LABEL = {1: "Seg", 2: "Ter", 3: "Qua", 4: "Qui", 5: "Sex", 6: "Sáb", 7: "Dom"}
# Cor padrão por área quando o aluno não escolhe uma.
AREA_COLOR = {
    "LC": "#2563eb",
    "CH": "#d97706",
    "CN": "#059669",
    "MT": "#7c3aed",
    "CP": "#be123c",
}
DEFAULT_COLOR = "#64748b"


def _hours(start: time, end: time) -> float:
    delta = datetime.combine(date.min, end) - datetime.combine(date.min, start)
    return delta.total_seconds() / 3600


# ---- planos -------------------------------------------------------------------


async def _owned_plan(session: AsyncSession, user: User, plan_id: uuid.UUID) -> StudyPlan:
    plan = await session.get(StudyPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise NotFoundError("Cronograma não encontrado.")
    return plan


async def _blocks(session: AsyncSession, plan_id: uuid.UUID) -> list[StudyBlock]:
    return list(
        (
            await session.scalars(
                select(StudyBlock)
                .where(StudyBlock.plan_id == plan_id)
                .order_by(StudyBlock.weekday, StudyBlock.start_time)
            )
        ).all()
    )


async def _lookups(session: AsyncSession):
    areas = {a.id: a for a in await session.scalars(select(KnowledgeArea))}
    subjects = {s.id: s for s in await session.scalars(select(Subject))}
    return areas, subjects


def _block_out(b: StudyBlock, areas, subjects) -> BlockOut:
    subject = subjects.get(b.subject_id) if b.subject_id else None
    area_id = b.area_id or (subject.area_id if subject else None)
    area = areas.get(area_id) if area_id else None
    return BlockOut(
        id=b.id,
        weekday=b.weekday,
        start_time=b.start_time,
        end_time=b.end_time,
        area_id=b.area_id,
        area_code=area.code if area else None,
        subject_id=b.subject_id,
        subject_name=subject.name if subject else None,
        title=b.title,
        color=b.color or (AREA_COLOR.get(area.code) if area else None) or DEFAULT_COLOR,
        notes=b.notes,
        reminder_minutes_before=b.reminder_minutes_before,
    )


async def plan_out(session: AsyncSession, plan: StudyPlan) -> PlanOut:
    areas, subjects = await _lookups(session)
    return PlanOut(
        id=plan.id,
        name=plan.name,
        is_active=plan.is_active,
        grid_start=plan.grid_start,
        grid_end=plan.grid_end,
        created_at=plan.created_at,
        blocks=[_block_out(b, areas, subjects) for b in await _blocks(session, plan.id)],
    )


async def list_plans(session: AsyncSession, user: User) -> list[PlanListItem]:
    plans = (
        await session.scalars(
            select(StudyPlan)
            .where(StudyPlan.user_id == user.id)
            .order_by(StudyPlan.is_active.desc(), StudyPlan.created_at)
        )
    ).all()
    out = []
    for p in plans:
        blocks = await _blocks(session, p.id)
        out.append(
            PlanListItem(
                id=p.id,
                name=p.name,
                is_active=p.is_active,
                block_count=len(blocks),
                weekly_hours=round(sum(_hours(b.start_time, b.end_time) for b in blocks), 2),
            )
        )
    return out


async def create_plan(session: AsyncSession, user: User, data: PlanIn) -> StudyPlan:
    has_active = await session.scalar(
        select(StudyPlan.id).where(StudyPlan.user_id == user.id, StudyPlan.is_active)
    )
    plan = StudyPlan(
        user_id=user.id,
        name=data.name.strip(),
        grid_start=data.grid_start,
        grid_end=data.grid_end,
        is_active=has_active is None,  # o primeiro cronograma já nasce ativo
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return plan


async def get_active(session: AsyncSession, user: User) -> StudyPlan:
    plan = await session.scalar(
        select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.is_active)
    )
    if plan is None:
        raise NotFoundError("Você ainda não tem um cronograma ativo.", code="no_active_plan")
    return plan


async def update_plan(
    session: AsyncSession, user: User, plan_id: uuid.UUID, data: PlanUpdate
) -> StudyPlan:
    plan = await _owned_plan(session, user, plan_id)
    fields = data.model_dump(exclude_unset=True)
    for key in ("name", "grid_start", "grid_end"):
        if fields.get(key) is not None:
            setattr(plan, key, fields[key].strip() if key == "name" else fields[key])
    if plan.grid_end <= plan.grid_start:
        raise AppError("invalid_grid", "O fim da grade deve ser depois do início.", 422)
    await session.commit()
    await session.refresh(plan)
    return plan


async def activate(session: AsyncSession, user: User, plan_id: uuid.UUID) -> StudyPlan:
    plan = await _owned_plan(session, user, plan_id)
    # Mesma transação: desativa todos e ativa o escolhido (índice único parcial).
    await session.execute(
        update(StudyPlan)
        .where(StudyPlan.user_id == user.id, StudyPlan.is_active)
        .values(is_active=False)
        .execution_options(synchronize_session=False)
    )
    await session.execute(
        update(StudyPlan)
        .where(StudyPlan.id == plan.id)
        .values(is_active=True)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    await session.refresh(plan)
    return plan


async def duplicate(session: AsyncSession, user: User, plan_id: uuid.UUID) -> StudyPlan:
    plan = await _owned_plan(session, user, plan_id)
    copy = StudyPlan(
        user_id=user.id,
        name=f"{plan.name} (cópia)"[:80],
        grid_start=plan.grid_start,
        grid_end=plan.grid_end,
        is_active=False,
    )
    session.add(copy)
    await session.flush()
    for b in await _blocks(session, plan.id):
        session.add(
            StudyBlock(
                plan_id=copy.id,
                weekday=b.weekday,
                start_time=b.start_time,
                end_time=b.end_time,
                area_id=b.area_id,
                subject_id=b.subject_id,
                title=b.title,
                color=b.color,
                notes=b.notes,
                reminder_minutes_before=b.reminder_minutes_before,
            )
        )
    await session.commit()
    await session.refresh(copy)
    return copy


async def delete_plan(session: AsyncSession, user: User, plan_id: uuid.UUID) -> None:
    plan = await _owned_plan(session, user, plan_id)
    await session.delete(plan)
    await session.commit()


# ---- blocos -------------------------------------------------------------------


async def _validate_block(
    session: AsyncSession,
    plan: StudyPlan,
    values: dict,
    exclude_id: uuid.UUID | None = None,
) -> None:
    start, end = values["start_time"], values["end_time"]
    if end <= start:
        raise AppError(
            "invalid_block_time",
            "O bloco deve terminar depois de começar (blocos não cruzam a meia-noite).",
            422,
        )
    if (
        values.get("area_id") is None
        and values.get("subject_id") is None
        and not values.get("title")
    ):
        raise AppError("block_needs_label", "Informe a área, a disciplina ou um título.", 422)
    if (
        values.get("area_id") is not None
        and await session.get(KnowledgeArea, values["area_id"]) is None
    ):
        raise AppError("invalid_area", "Área inválida.", 422)
    if values.get("subject_id") is not None:
        subject = await session.get(Subject, values["subject_id"])
        if subject is None:
            raise AppError("invalid_subject", "Disciplina inválida.", 422)
        if values.get("area_id") is not None and subject.area_id != values["area_id"]:
            raise AppError(
                "subject_area_mismatch", "A disciplina não pertence à área escolhida.", 422
            )
    # Sobreposição: novo.start < existente.end AND novo.end > existente.start (mesmo dia).
    stmt = select(StudyBlock).where(
        StudyBlock.plan_id == plan.id,
        StudyBlock.weekday == values["weekday"],
        StudyBlock.start_time < end,
        StudyBlock.end_time > start,
    )
    if exclude_id is not None:
        stmt = stmt.where(StudyBlock.id != exclude_id)
    conflict = await session.scalar(stmt.limit(1))
    if conflict is not None:
        areas, subjects = await _lookups(session)
        raise AppError(
            "block_overlap",
            "Esse horário se sobrepõe a outro bloco do mesmo dia.",
            409,
            {"conflict": _block_out(conflict, areas, subjects).model_dump(mode="json")},
        )


async def create_block(
    session: AsyncSession, user: User, plan_id: uuid.UUID, data: BlockIn
) -> StudyBlock:
    plan = await _owned_plan(session, user, plan_id)
    values = data.model_dump()
    await _validate_block(session, plan, values)
    block = StudyBlock(plan_id=plan.id, **values)
    session.add(block)
    await session.commit()
    await session.refresh(block)
    return block


async def update_block(
    session: AsyncSession, user: User, plan_id: uuid.UUID, block_id: uuid.UUID, data: BlockUpdate
) -> StudyBlock:
    plan = await _owned_plan(session, user, plan_id)
    block = await session.get(StudyBlock, block_id)
    if block is None or block.plan_id != plan.id:
        raise NotFoundError("Bloco não encontrado.")
    fields = data.model_dump(exclude_unset=True)
    for key in ("start_time", "end_time"):
        if fields.get(key) is not None and (fields[key].minute % 5 or fields[key].second):
            raise AppError("invalid_block_time", "Use horários em múltiplos de 5 minutos.", 422)
    if "color" in fields and fields["color"] is not None:
        if not HEX_RE.match(fields["color"]):
            raise AppError("invalid_color", "Cor deve estar no formato #RRGGBB.", 422)
    values = {
        c: getattr(block, c)
        for c in (
            "weekday",
            "start_time",
            "end_time",
            "area_id",
            "subject_id",
            "title",
            "color",
            "notes",
            "reminder_minutes_before",
        )
    }
    for key, value in fields.items():
        if key in ("weekday", "start_time", "end_time") and value is None:
            continue
        values[key] = (
            value.strip() or None if isinstance(value, str) and key in ("title", "notes") else value
        )
    await _validate_block(session, plan, values, exclude_id=block.id)
    for key, value in values.items():
        setattr(block, key, value)
    await session.commit()
    await session.refresh(block)
    return block


async def delete_block(
    session: AsyncSession, user: User, plan_id: uuid.UUID, block_id: uuid.UUID
) -> None:
    plan = await _owned_plan(session, user, plan_id)
    block = await session.get(StudyBlock, block_id)
    if block is None or block.plan_id != plan.id:
        raise NotFoundError("Bloco não encontrado.")
    await session.delete(block)
    await session.commit()


async def block_out(session: AsyncSession, block: StudyBlock) -> BlockOut:
    areas, subjects = await _lookups(session)
    return _block_out(block, areas, subjects)


# ---- resumo -------------------------------------------------------------------


async def summary(session: AsyncSession, user: User, plan_id: uuid.UUID) -> PlanSummary:
    plan = await _owned_plan(session, user, plan_id)
    areas, subjects = await _lookups(session)
    by_area: dict[str, float] = defaultdict(float)
    by_day: dict[int, float] = defaultdict(float)
    for b in await _blocks(session, plan.id):
        h = _hours(b.start_time, b.end_time)
        out = _block_out(b, areas, subjects)
        by_area[out.area_code or "OUTRO"] += h
        by_day[b.weekday] += h
    area_names = {a.code: a.name for a in areas.values()}
    return PlanSummary(
        total_hours=round(sum(by_day.values()), 2),
        by_area=[
            HoursBy(key=code, label=area_names.get(code, "Outros"), hours=round(h, 2))
            for code, h in sorted(by_area.items(), key=lambda kv: -kv[1])
        ],
        by_day=[
            HoursBy(key=str(d), label=WEEKDAY_LABEL[d], hours=round(by_day.get(d, 0.0), 2))
            for d in range(1, 8)
        ],
    )


async def get_plan(session: AsyncSession, user: User, plan_id: uuid.UUID) -> StudyPlan:
    return await _owned_plan(session, user, plan_id)
