from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.models import Job


async def enqueue(
    session: AsyncSession,
    queue: str,
    payload: dict[str, Any] | None = None,
    *,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> Job:
    """Insere um job na transação de quem chama: se ela der rollback, o job some junto."""
    job = Job(queue=queue, payload=payload or {}, max_attempts=max_attempts)
    if run_after is not None:
        job.run_after = run_after
    session.add(job)
    await session.flush()
    return job
