from datetime import timedelta

import pytest
from sqlalchemy import delete, select, text, update

from app.core.enums import JobStatus
from app.jobs import registry
from app.jobs.models import Job
from app.jobs.queue import enqueue
from app.jobs.runner import (
    claim_next,
    mark_failed_or_retry,
    process_next,
    recover_stuck,
)


@pytest.fixture
def handlers():
    calls = []

    async def ok(session, payload, job):
        calls.append(payload)

    async def boom(session, payload, job):
        await enqueue(session, "test.side_effect", {})  # deve ser desfeito no erro
        raise RuntimeError("falhou")

    registry.HANDLERS["test.ok"] = ok
    registry.HANDLERS["test.boom"] = boom
    yield calls
    registry.HANDLERS.pop("test.ok")
    registry.HANDLERS.pop("test.boom")


async def _get(db, job_id) -> Job:
    db.expire_all()
    return await db.get(Job, job_id)


async def test_enqueue_e_claim(db):
    job = await enqueue(db, "test.ok", {"a": 1})
    claimed = await claim_next(db)
    assert claimed.id == job.id
    assert claimed.status == JobStatus.running
    assert claimed.attempts == 1
    assert await claim_next(db) is None


async def test_nao_pega_job_agendado_para_o_futuro(db):
    await enqueue(
        db, "test.ok", run_after=await db.scalar(text("SELECT now() + interval '1 hour'"))
    )
    assert await claim_next(db) is None


async def test_process_next_sucesso(db, session_factory, handlers):
    job = await enqueue(db, "test.ok", {"x": 1})
    await db.commit()
    assert await process_next(session_factory) is True
    assert handlers == [{"x": 1}]
    assert (await _get(db, job.id)).status == JobStatus.done
    assert await process_next(session_factory) is False


async def test_erro_faz_retry_com_backoff_e_desfaz_efeitos(db, session_factory, handlers):
    job = await enqueue(db, "test.boom")
    await db.commit()
    await process_next(session_factory)

    refreshed = await _get(db, job.id)
    assert refreshed.status == JobStatus.pending
    assert refreshed.attempts == 1
    assert "RuntimeError: falhou" in refreshed.last_error
    delay = refreshed.run_after - await db.scalar(text("SELECT now()"))
    assert timedelta(seconds=59) < delay <= timedelta(seconds=60)  # 2^1 * 30s
    side = await db.scalar(select(Job).where(Job.queue == "test.side_effect"))
    assert side is None


async def test_vira_failed_apos_max_attempts(db):
    job = await enqueue(db, "test.boom", max_attempts=2)
    await claim_next(db)
    assert await mark_failed_or_retry(db, job.id, "e1") == JobStatus.pending
    await db.execute(update(Job).where(Job.id == job.id).values(run_after=text("now()")))
    await claim_next(db)
    assert await mark_failed_or_retry(db, job.id, "e2") == JobStatus.failed


async def test_fila_sem_handler_falha(db, session_factory):
    job = await enqueue(db, "fila.inexistente", max_attempts=1)
    await db.commit()
    await process_next(session_factory)
    refreshed = await _get(db, job.id)
    assert refreshed.status == JobStatus.failed
    assert "LookupError" in refreshed.last_error


async def test_recupera_jobs_presos(db):
    job = await enqueue(db, "test.ok")
    await claim_next(db)
    assert await recover_stuck(db) == 0
    await db.execute(
        update(Job).where(Job.id == job.id).values(locked_at=text("now() - interval '11 minutes'"))
    )
    assert await recover_stuck(db) == 1
    refreshed = await _get(db, job.id)
    assert refreshed.status == JobStatus.pending
    assert refreshed.locked_at is None


async def test_skip_locked_entre_conexoes(engine):
    """Dois workers concorrentes nunca pegam o mesmo job (dados commitados de verdade)."""
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as setup:
        a = await enqueue(setup, "test.concorrencia")
        b = await enqueue(setup, "test.concorrencia")
        ids = {a.id, b.id}
        await setup.commit()
    try:
        async with AsyncSession(engine) as w1, AsyncSession(engine) as w2:
            j1 = await claim_next(w1)  # transação aberta: linha travada
            j2 = await claim_next(w2)
            j3 = await claim_next(w2)
            assert {j1.id, j2.id} == ids
            assert j3 is None
            await w1.rollback()
            await w2.rollback()
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(delete(Job).where(Job.id.in_(ids)))
            await cleanup.commit()
