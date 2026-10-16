"""Painel do aluno e relatório de custo de IA."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import EssayStatus
from app.modules.essays.models import Essay, EssayResult, EssayTheme
from app.modules.planner import service as planner
from app.modules.planner.models import StudyBlock, StudyPlan
from app.modules.questions.models import QuestionAttempt
from app.modules.stats.schemas import (
    DashboardOut,
    LastEssay,
    WeekAccuracy,
)
from app.modules.users.models import User


def _tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("America/Sao_Paulo")


async def _activity_days(
    session: AsyncSession, user: User, tz: ZoneInfo, since: datetime
) -> set[date]:
    """Dias (no fuso do aluno) com alguma atividade: questão respondida ou redação enviada."""
    tzname = str(tz)
    q_days = select(cast(func.timezone(tzname, QuestionAttempt.answered_at), Date)).where(
        QuestionAttempt.user_id == user.id, QuestionAttempt.answered_at >= since
    )
    e_days = select(cast(func.timezone(tzname, Essay.created_at), Date)).where(
        Essay.user_id == user.id, Essay.created_at >= since
    )
    days = set((await session.scalars(q_days.union(e_days))).all())
    return days


def streak(days: set[date], today: date) -> int:
    """Dias seguidos estudando, terminando hoje (ou ontem, se hoje ainda não estudou)."""
    current = today if today in days else today - timedelta(days=1)
    count = 0
    while current in days:
        count += 1
        current -= timedelta(days=1)
    return count


async def dashboard(session: AsyncSession, user: User, now: datetime | None = None) -> DashboardOut:
    now = now or datetime.now(UTC)
    tz = _tz(user)
    local_now = now.astimezone(tz)
    today = local_now.date()
    weekday = today.isoweekday()

    # blocos de hoje do cronograma ativo
    blocks = (
        await session.scalars(
            select(StudyBlock)
            .join(StudyPlan, StudyPlan.id == StudyBlock.plan_id)
            .where(StudyPlan.user_id == user.id, StudyPlan.is_active, StudyBlock.weekday == weekday)
            .order_by(StudyBlock.start_time)
        )
    ).all()
    out_blocks = [await planner.block_out(session, b) for b in blocks]
    now_t = local_now.time().replace(tzinfo=None)
    next_block = next((b for b in blocks if b.end_time > now_t), None)

    # última redação
    row = (
        await session.execute(
            select(Essay, EssayTheme.title, EssayResult.total)
            .outerjoin(EssayTheme, EssayTheme.id == Essay.theme_id)
            .outerjoin(EssayResult, EssayResult.essay_id == Essay.id)
            .where(Essay.user_id == user.id)
            .order_by(Essay.created_at.desc())
            .limit(1)
        )
    ).first()
    last_essay = None
    if row:
        essay, title, total = row
        last_essay = LastEssay(
            id=essay.id,
            theme_title=title or essay.custom_theme or "Tema removido",
            status=essay.status,
            total=total,
            created_at=essay.created_at,
        )
    graded = await session.scalar(
        select(func.count())
        .select_from(Essay)
        .where(Essay.user_id == user.id, Essay.status == EssayStatus.graded)
    )

    # acerto da semana (segunda 00:00 no fuso do aluno até agora), todas as tentativas
    week_start = datetime.combine(today - timedelta(days=weekday - 1), time(0), tzinfo=tz)
    answered, correct = (
        await session.execute(
            select(func.count(), func.count().filter(QuestionAttempt.is_correct)).where(
                QuestionAttempt.user_id == user.id, QuestionAttempt.answered_at >= week_start
            )
        )
    ).one()

    days = await _activity_days(session, user, tz, now - timedelta(days=400))
    return DashboardOut(
        today=today,
        weekday=weekday,
        today_blocks=out_blocks,
        next_block_id=next_block.id if next_block else None,
        last_essay=last_essay,
        essays_graded=graded or 0,
        week_accuracy=WeekAccuracy(
            answered=answered,
            correct=correct,
            pct=round(100 * correct / answered, 1) if answered else None,
        ),
        streak_days=streak(days, today),
        studied_today=today in days,
    )
