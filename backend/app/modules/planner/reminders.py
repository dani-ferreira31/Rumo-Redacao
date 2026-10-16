"""Lembretes de estudo por e-mail, no fuso de cada usuário.

O worker chama `send_due_reminders` a cada minuto. Um lembrete dispara quando
`início do bloco − reminder_minutes_before` cai na janela (agora − WINDOW, agora].
A janela cobre ticks atrasados; a deduplicação (`email_logs.dedupe_key =
reminder:{bloco}:{data local}`) garante um único e-mail por ocorrência.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.email.service import queue_email, unsubscribe_url
from app.modules.planner.models import StudyBlock, StudyPlan
from app.modules.questions.models import KnowledgeArea, Subject
from app.modules.system.settings import feature_enabled
from app.modules.users.models import User

logger = logging.getLogger(__name__)

WINDOW = timedelta(minutes=10)
WEEKDAY_NAME = {
    1: "segunda",
    2: "terça",
    3: "quarta",
    4: "quinta",
    5: "sexta",
    6: "sábado",
    7: "domingo",
}


def next_fire(block: StudyBlock, tz: ZoneInfo, now: datetime) -> tuple[datetime, date] | None:
    """Disparo do lembrete que cai na janela atual, com a data local da ocorrência."""
    local_now = now.astimezone(tz)
    # o lembrete pode ser até 24 h antes: a ocorrência é hoje ou amanhã (no fuso do aluno)
    for offset in (0, 1):
        day = local_now.date() + timedelta(days=offset)
        if day.isoweekday() != block.weekday:
            continue
        start = datetime.combine(day, block.start_time, tzinfo=tz)
        fire = start - timedelta(minutes=block.reminder_minutes_before or 0)
        if now - WINDOW < fire <= now:
            return fire, day
    return None


def _label(block: StudyBlock, subjects: dict, areas: dict) -> str:
    parts = []
    if block.subject_id and block.subject_id in subjects:
        parts.append(subjects[block.subject_id].name)
    elif block.area_id and block.area_id in areas:
        parts.append(areas[block.area_id].name)
    if block.title:
        parts.append(block.title)
    return " · ".join(parts) or "Estudo"


async def send_due_reminders(session: AsyncSession, now: datetime | None = None) -> int:
    if not (
        await feature_enabled(session, "email_reminders")
        and await feature_enabled(session, "planner")
    ):
        return 0
    now = now or datetime.now(UTC)
    rows = (
        await session.execute(
            select(StudyBlock, User)
            .join(StudyPlan, StudyPlan.id == StudyBlock.plan_id)
            .join(User, User.id == StudyPlan.user_id)
            .where(
                StudyPlan.is_active,
                StudyBlock.reminder_minutes_before.is_not(None),
                User.email_reminders_enabled,
                User.email_verified_at.is_not(None),
            )
        )
    ).all()
    if not rows:
        return 0
    subjects = {s.id: s for s in await session.scalars(select(Subject))}
    areas = {a.id: a for a in await session.scalars(select(KnowledgeArea))}
    app_url = get_settings().app_url
    queued = 0
    for block, user in rows:
        try:
            tz = ZoneInfo(user.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            tz = ZoneInfo("America/Sao_Paulo")
        hit = next_fire(block, tz, now)
        if hit is None:
            continue
        _, day = hit
        label = _label(block, subjects, areas)
        start = block.start_time.strftime("%H:%M")
        log_id = await queue_email(
            session,
            user_id=user.id,
            to=user.email,
            type="study_reminder",
            subject=f"Lembrete: {label} às {start}",
            template="study_reminder.html",
            context={
                "name": user.name,
                "label": label,
                "start": start,
                "end": block.end_time.strftime("%H:%M"),
                "weekday": WEEKDAY_NAME[block.weekday],
                "minutes": block.reminder_minutes_before,
                "notes": block.notes,
                "url": f"{app_url}/cronograma",
                "unsubscribe_url": unsubscribe_url(user.id),
            },
            dedupe_key=f"reminder:{block.id}:{day.isoformat()}",
        )
        if log_id is not None:
            queued += 1
    await session.commit()
    if queued:
        logger.info("reminders_queued", extra={"extra_fields": {"count": queued}})
    return queued
