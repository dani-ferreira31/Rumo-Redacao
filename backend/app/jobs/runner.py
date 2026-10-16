"""Operações da fila (Postgres + FOR UPDATE SKIP LOCKED). Ver docs/02-arquitetura.md."""

import logging
from datetime import timedelta

from sqlalchemy import case, func, literal, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.enums import JobStatus
from app.core.logging import bind_log_context, log_context
from app.jobs.models import Job
from app.jobs.registry import HANDLERS

logger = logging.getLogger(__name__)

BACKOFF_BASE = timedelta(seconds=30)
STUCK_AFTER = timedelta(minutes=10)


def _status(value: JobStatus):
    # literal tipado: dentro de CASE o Postgres não infere o enum sozinho
    return literal(value, Job.__table__.c.status.type)


def _next_status_after_failure():
    return case(
        (Job.attempts >= Job.max_attempts, _status(JobStatus.failed)),
        else_=_status(JobStatus.pending),
    )


async def claim_next(session: AsyncSession) -> Job | None:
    """Pega o próximo job pendente, marcando-o como `running` e incrementando `attempts`."""
    next_id = (
        select(Job.id)
        .where(Job.status == JobStatus.pending, Job.run_after <= func.now())
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    stmt = (
        update(Job)
        .where(Job.id == next_id)
        .values(status=JobStatus.running, locked_at=func.now(), attempts=Job.attempts + 1)
        .returning(Job)
        .execution_options(synchronize_session=False, populate_existing=True)
    )
    return (await session.scalars(stmt)).one_or_none()


async def mark_done(session: AsyncSession, job_id: int) -> None:
    await session.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status=JobStatus.done, locked_at=None, last_error=None)
        .execution_options(synchronize_session=False)
    )


async def mark_failed_or_retry(session: AsyncSession, job_id: int, error: str) -> JobStatus:
    """Volta para `pending` com backoff exponencial (2^attempts * 30s) ou vira `failed`."""
    exhausted = Job.attempts >= Job.max_attempts
    stmt = (
        update(Job)
        .where(Job.id == job_id)
        .values(
            status=_next_status_after_failure(),
            run_after=case(
                (exhausted, Job.run_after),
                else_=func.now() + BACKOFF_BASE * func.power(2, Job.attempts),
            ),
            locked_at=None,
            last_error=error[:4000],
        )
        .returning(Job.status)
        .execution_options(synchronize_session=False)
    )
    return (await session.execute(stmt)).scalar_one()


async def recover_stuck(session: AsyncSession, older_than: timedelta = STUCK_AFTER) -> int:
    """Jobs presos em `running` (worker morreu) voltam para `pending` (ou `failed`)."""
    stmt = (
        update(Job)
        .where(Job.status == JobStatus.running, Job.locked_at < func.now() - older_than)
        .values(
            status=_next_status_after_failure(),
            locked_at=None,
            last_error="Recuperado após ficar preso em running",
        )
        .execution_options(synchronize_session=False)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def run_job(session: AsyncSession, job: Job) -> None:
    handler = HANDLERS.get(job.queue)
    if handler is None:
        raise LookupError(f"Nenhum handler registrado para a fila {job.queue!r}")
    await handler(session, job.payload, job)


async def process_next(session_factory: async_sessionmaker[AsyncSession]) -> bool:
    """Processa um job. Retorna False se a fila estava vazia.

    O claim é commitado separado; o trabalho do handler e o `done` vão na mesma
    transação, de modo que um erro desfaz tudo o que o handler fez.
    """
    async with session_factory() as session:
        job = await claim_next(session)
        await session.commit()
    if job is None:
        return False

    token = log_context.set(dict(log_context.get() or {}))
    bind_log_context(job_id=job.id, queue=job.queue)
    try:
        async with session_factory() as session:
            try:
                await run_job(session, job)
                await mark_done(session, job.id)
                await session.commit()
                logger.info("job_done", extra={"extra_fields": {"attempt": job.attempts}})
                return True
            except Exception as exc:
                await session.rollback()
                status = await mark_failed_or_retry(session, job.id, f"{type(exc).__name__}: {exc}")
                await session.commit()
                logger.exception(
                    "job_error", extra={"extra_fields": {"attempt": job.attempts, "status": status}}
                )
                return True
    finally:
        log_context.reset(token)
