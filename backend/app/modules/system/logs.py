"""Admin → Logs: avisos e erros gravados por `app/core/applog.py` (já sem dados pessoais)."""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.modules.system.models import AppLog
from app.modules.system.settings import get_setting, log_event, set_setting
from app.modules.users.models import User

LevelFilter = Literal["WARNING", "ERROR"]
SourceFilter = Literal["api", "worker"]


class LogItem(BaseModel):
    id: int
    created_at: datetime
    level: str
    source: str
    logger: str
    event: str
    error: str | None
    path: str | None
    request_id: str | None
    has_traceback: bool


class LogDetail(LogItem):
    traceback: str | None
    details: dict[str, Any]


class TopError(BaseModel):
    event: str
    error: str | None
    count: int
    last_at: datetime


class LogSummary(BaseModel):
    errors_24h: int
    warnings_24h: int
    errors_7d: int
    top_24h: list[TopError]


class LogsOut(BaseModel):
    items: list[LogItem]
    next_before_id: int | None
    summary: LogSummary
    retention_days: int


class LogSettings(BaseModel):
    retention_days: int = Field(ge=1, le=180)


def _item(row: AppLog) -> LogItem:
    return LogItem(
        id=row.id,
        created_at=row.created_at,
        level=row.level,
        source=row.source,
        logger=row.logger,
        event=row.event,
        error=row.error,
        path=row.path,
        request_id=row.request_id,
        has_traceback=bool(row.traceback),
    )


async def _summary(session: AsyncSession) -> LogSummary:
    now = datetime.now(UTC)
    d1, d7 = now - timedelta(days=1), now - timedelta(days=7)
    is_error = AppLog.level.in_(("ERROR", "CRITICAL"))
    errors_24h, warnings_24h, errors_7d = (
        await session.execute(
            select(
                func.count().filter(is_error, AppLog.created_at >= d1),
                func.count().filter(AppLog.level == "WARNING", AppLog.created_at >= d1),
                func.count().filter(is_error),
            ).where(AppLog.created_at >= d7)
        )
    ).one()
    # erro "principal" sem a mensagem variável: agrupa pelo tipo da exceção
    error_type = func.split_part(AppLog.error, ":", 1)
    top = await session.execute(
        select(AppLog.event, error_type, func.count(), func.max(AppLog.created_at))
        .where(is_error, AppLog.created_at >= d1)
        .group_by(AppLog.event, error_type)
        .order_by(func.count().desc())
        .limit(5)
    )
    return LogSummary(
        errors_24h=errors_24h or 0,
        warnings_24h=warnings_24h or 0,
        errors_7d=errors_7d or 0,
        top_24h=[TopError(event=e, error=t or None, count=n, last_at=at) for e, t, n, at in top],
    )


async def list_logs(
    session: AsyncSession,
    level: LevelFilter | None,
    source: SourceFilter | None,
    q: str | None,
    before_id: int | None,
    limit: int,
) -> LogsOut:
    stmt = select(AppLog)
    if level == "ERROR":
        stmt = stmt.where(AppLog.level.in_(("ERROR", "CRITICAL")))
    elif level == "WARNING":
        stmt = stmt.where(AppLog.level == "WARNING")
    if source:
        stmt = stmt.where(AppLog.source == source)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                AppLog.event.ilike(term),
                AppLog.error.ilike(term),
                AppLog.path.ilike(term),
                AppLog.request_id.ilike(term),
            )
        )
    if before_id:
        stmt = stmt.where(AppLog.id < before_id)
    rows = list(await session.scalars(stmt.order_by(AppLog.id.desc()).limit(limit + 1)))
    retention = int((await get_setting(session, "logs"))["retention_days"])
    return LogsOut(
        items=[_item(r) for r in rows[:limit]],
        next_before_id=rows[limit - 1].id if len(rows) > limit else None,
        summary=await _summary(session),
        retention_days=retention,
    )


async def get_log(session: AsyncSession, log_id: int) -> LogDetail:
    row = await session.get(AppLog, log_id)
    if row is None:
        raise NotFoundError("Registro não encontrado.")
    return LogDetail(**_item(row).model_dump(), traceback=row.traceback, details=row.details or {})


async def set_retention(session: AsyncSession, admin: User, data: LogSettings) -> LogSettings:
    await set_setting(session, "logs", data.model_dump(), admin.id)
    log_event(session, "logs", f"Retenção dos logs: {data.retention_days} dias")
    cutoff = datetime.now(UTC) - timedelta(days=data.retention_days)
    await session.execute(delete(AppLog).where(AppLog.created_at < cutoff))
    await session.commit()
    return data


async def clear_logs(session: AsyncSession) -> int:
    result = await session.execute(delete(AppLog))
    log_event(session, "logs", f"Logs apagados pelo admin ({result.rowcount or 0} registros)")
    await session.commit()
    return result.rowcount or 0
