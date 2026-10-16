"""Worker: processa a fila `jobs` e roda tarefas periódicas.

Uso: python -m app.worker
"""

import asyncio
import logging
import signal
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import app.models  # noqa: F401  (registra todas as tabelas no SQLAlchemy)
from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.logging import configure_logging
from app.jobs.registry import load_handlers
from app.jobs.runner import process_next, recover_stuck
from app.modules.planner.reminders import send_due_reminders
from app.modules.system.budget import send_budget_alerts
from app.modules.system.service import record_heartbeat

logger = logging.getLogger("app.worker")


@dataclass
class PeriodicTask:
    name: str
    interval_seconds: float
    fn: Callable[[], Awaitable[None]]
    last_run: float = 0.0


async def _recover_stuck() -> None:
    async with SessionLocal() as session:
        count = await recover_stuck(session)
        await session.commit()
    if count:
        logger.warning("jobs_recovered", extra={"extra_fields": {"count": count}})


async def _study_reminders() -> None:
    async with SessionLocal() as session:
        await send_due_reminders(session)


async def _heartbeat() -> None:
    async with SessionLocal() as session:
        await record_heartbeat(session)


async def _budget_alerts() -> None:
    async with SessionLocal() as session:
        await send_budget_alerts(session)


PERIODIC_TASKS: list[PeriodicTask] = [
    PeriodicTask("heartbeat", 30, _heartbeat),
    PeriodicTask("recover_stuck", 60, _recover_stuck),
    PeriodicTask("study_reminders", 60, _study_reminders),
    PeriodicTask("budget_alerts", 600, _budget_alerts),
]


async def _run_periodic() -> None:
    now = time.monotonic()
    for task in PERIODIC_TASKS:
        if now - task.last_run >= task.interval_seconds:
            task.last_run = now
            try:
                await task.fn()
            except Exception:
                logger.exception("periodic_task_error", extra={"extra_fields": {"task": task.name}})


async def run_worker(stop: asyncio.Event) -> None:
    settings = get_settings()
    handlers = load_handlers()
    logger.info("worker_started", extra={"extra_fields": {"queues": sorted(handlers)}})
    while not stop.is_set():
        await _run_periodic()
        try:
            processed = await process_next(SessionLocal)
        except Exception:
            logger.exception("worker_loop_error")
            processed = False
        if not processed:
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval)
            except TimeoutError:
                pass
    logger.info("worker_stopped")


async def main() -> None:
    configure_logging(get_settings().log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    try:
        await run_worker(stop)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
