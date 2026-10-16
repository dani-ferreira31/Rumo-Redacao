"""Cota do plano gratuito dos provedores de IA (ex.: Gemini Flash-Lite).

O Google não tem API que informe o saldo da cota. O app conta o próprio uso em
`ai_usage` e compara com os limites que o admin cadastra (requisições por
minuto e por dia, tokens de entrada por minuto). O dia da cota do Google vira à
meia-noite do horário do Pacífico.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AIUsage
from app.modules.system.settings import get_setting, log_event, set_setting
from app.modules.users.models import User

QUOTA_TZ = ZoneInfo("America/Los_Angeles")
WARN_PCT = 80
HISTORY_DAYS = 7

Level = Literal["ok", "warning", "error"]


class QuotaRule(BaseModel):
    provider: Literal["anthropic", "openai", "google"]
    model_match: str = Field(
        min_length=1, max_length=100, description="Trecho do nome do modelo (ex.: flash-lite)"
    )
    rpm: int | None = Field(default=None, ge=1, description="Requisições por minuto")
    tpm: int | None = Field(default=None, ge=1, description="Tokens de entrada por minuto")
    rpd: int | None = Field(default=None, ge=1, description="Requisições por dia")


class QuotasIn(BaseModel):
    quotas: list[QuotaRule] = Field(max_length=10)


class Meter(BaseModel):
    used: int
    limit: int | None
    pct: float | None


class QuotaDay(BaseModel):
    day: date
    requests: int
    input_tokens: int
    output_tokens: int


class QuotaUsage(BaseModel):
    rule: QuotaRule
    models: list[str] = Field(description="Modelos reais que casaram (o alias vira a versão)")
    rpm: Meter
    tpm: Meter
    rpd: Meter
    peak_rpm_today: int
    input_tokens_today: int
    output_tokens_today: int
    day_resets_at: datetime
    level: Level
    history: list[QuotaDay]


class QuotasOut(BaseModel):
    quotas: list[QuotaUsage]


def quota_day_start(now: datetime) -> datetime:
    local = now.astimezone(QUOTA_TZ)
    return datetime(local.year, local.month, local.day, tzinfo=QUOTA_TZ)


def _meter(used: int, limit: int | None) -> Meter:
    return Meter(used=used, limit=limit, pct=round(100 * used / limit, 1) if limit else None)


def _level(*meters: Meter) -> Level:
    pcts = [m.pct for m in meters if m.pct is not None]
    if any(p >= 100 for p in pcts):
        return "error"
    if any(p >= WARN_PCT for p in pcts):
        return "warning"
    return "ok"


async def rules(session: AsyncSession) -> list[QuotaRule]:
    return [QuotaRule(**r) for r in await get_setting(session, "ai_quotas") or []]


async def usage(session: AsyncSession, rule: QuotaRule, now: datetime | None = None) -> QuotaUsage:
    now = now or datetime.now(UTC)
    match = (AIUsage.provider == rule.provider) & AIUsage.model.ilike(f"%{rule.model_match}%")
    minute_ago = now - timedelta(minutes=1)
    day_start = quota_day_start(now)

    rpm_used, tpm_used = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(AIUsage.input_tokens), 0)).where(
                match, AIUsage.created_at > minute_ago
            )
        )
    ).one()
    rpd_used, input_today, output_today = (
        await session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(AIUsage.input_tokens), 0),
                func.coalesce(func.sum(AIUsage.output_tokens), 0),
            ).where(match, AIUsage.created_at >= day_start)
        )
    ).one()
    per_minute = (
        select(func.count().label("n"))
        .where(match, AIUsage.created_at >= day_start)
        .group_by(func.date_trunc("minute", AIUsage.created_at))
        .subquery()
    )
    peak = await session.scalar(select(func.coalesce(func.max(per_minute.c.n), 0)))

    local_day = func.date(func.timezone(str(QUOTA_TZ), AIUsage.created_at))
    since = day_start - timedelta(days=HISTORY_DAYS - 1)
    history = [
        QuotaDay(day=d, requests=n, input_tokens=i, output_tokens=o)
        for d, n, i, o in await session.execute(
            select(
                local_day,
                func.count(),
                func.coalesce(func.sum(AIUsage.input_tokens), 0),
                func.coalesce(func.sum(AIUsage.output_tokens), 0),
            )
            .where(match, AIUsage.created_at >= since)
            .group_by(local_day)
            .order_by(local_day)
        )
    ]
    models = sorted(await session.scalars(select(AIUsage.model).where(match).distinct()))

    rpm, tpm, rpd = (
        _meter(rpm_used, rule.rpm),
        _meter(tpm_used, rule.tpm),
        _meter(rpd_used, rule.rpd),
    )
    return QuotaUsage(
        rule=rule,
        models=models,
        rpm=rpm,
        tpm=tpm,
        rpd=rpd,
        peak_rpm_today=peak or 0,
        input_tokens_today=input_today,
        output_tokens_today=output_today,
        day_resets_at=(day_start + timedelta(days=1)).astimezone(UTC),
        level=_level(rpm, tpm, rpd),
        history=history,
    )


async def report(session: AsyncSession, now: datetime | None = None) -> QuotasOut:
    return QuotasOut(quotas=[await usage(session, r, now) for r in await rules(session)])


async def set_rules(session: AsyncSession, admin: User, data: QuotasIn) -> None:
    await set_setting(session, "ai_quotas", [r.model_dump() for r in data.quotas], admin.id)
    log_event(session, "ai", "Limites do plano gratuito de IA atualizados")
    await session.commit()
