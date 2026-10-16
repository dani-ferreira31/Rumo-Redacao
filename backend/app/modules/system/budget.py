"""Orçamento mensal de IA. O mês segue o fuso de São Paulo."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AIUsage
from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.errors import AppError
from app.email.service import queue_email
from app.modules.system.settings import get_setting, log_event
from app.modules.users.models import User

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Sao_Paulo")
WARN_PCT = 80


def month_start(now: datetime | None = None, months_back: int = 0) -> datetime:
    local = (now or datetime.now(UTC)).astimezone(TZ)
    year, month = local.year, local.month - months_back
    while month < 1:
        year, month = year - 1, month + 12
    return datetime(year, month, 1, tzinfo=TZ)


def next_month_start(start: datetime) -> datetime:
    return (start + timedelta(days=32)).replace(day=1)


@dataclass
class BudgetStatus:
    spent_usd: float
    budget_usd: float | None
    pct: float | None
    projected_usd: float
    warning: bool
    exceeded: bool


async def cost_between(session: AsyncSession, start: datetime, end: datetime) -> Decimal:
    value = await session.scalar(
        select(func.coalesce(func.sum(AIUsage.cost_usd), 0)).where(
            AIUsage.created_at >= start, AIUsage.created_at < end
        )
    )
    return Decimal(value or 0)


async def budget_status(session: AsyncSession, now: datetime | None = None) -> BudgetStatus:
    now = now or datetime.now(UTC)
    start = month_start(now)
    end = next_month_start(start)
    spent = await cost_between(session, start, end)
    budget = (await get_setting(session, "limits")).get("ai_budget_usd")
    elapsed = max((now - start).total_seconds(), 3600.0)
    projected = float(spent) * (end - start).total_seconds() / elapsed
    pct = round(100 * float(spent) / float(budget), 1) if budget else None
    return BudgetStatus(
        spent_usd=round(float(spent), 4),
        budget_usd=float(budget) if budget else None,
        pct=pct,
        projected_usd=round(projected, 2),
        warning=pct is not None and pct >= WARN_PCT,
        exceeded=pct is not None and pct >= 100,
    )


async def ensure_budget(session: AsyncSession, user: User | None = None) -> None:
    """Bloqueia novos trabalhos de IA quando o orçamento do mês acabou (o admin passa)."""
    if user is not None and user.role == UserRole.admin:
        return
    status = await budget_status(session)
    if status.exceeded:
        raise AppError(
            "ai_budget_exceeded",
            "A correção automática está pausada temporariamente. Tente novamente mais tarde.",
            503,
        )


async def send_budget_alerts(session: AsyncSession) -> None:
    """E-mail aos admins ao passar de 80% e de 100% (uma vez por mês cada)."""
    status = await budget_status(session)
    if not status.warning:
        return
    level = 100 if status.exceeded else WARN_PCT
    month = month_start().strftime("%Y-%m")
    admins = (await session.scalars(select(User).where(User.role == UserRole.admin))).all()
    sent = False
    for admin in admins:
        log_id = await queue_email(
            session,
            to=admin.email,
            type="budget_alert",
            subject=(
                "Orçamento de IA atingido"
                if status.exceeded
                else f"Gasto com IA em {status.pct:.0f}% do orçamento"
            ),
            template="budget_alert.html",
            context={
                "name": admin.name,
                "spent": status.spent_usd,
                "budget": status.budget_usd,
                "pct": round(status.pct or 0),
                "exceeded": status.exceeded,
                "url": f"{get_settings().app_url}/admin/custos",
            },
            user_id=admin.id,
            dedupe_key=f"budget{level}:{month}:{admin.id}",
        )
        sent = sent or log_id is not None
    if sent:
        log_event(session, "budget", f"Gasto com IA chegou a {status.pct:.0f}% do orçamento")
    await session.commit()
