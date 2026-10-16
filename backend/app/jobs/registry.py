"""Registro de handlers de jobs por nome de fila."""

import importlib
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.models import Job

JobHandler = Callable[[AsyncSession, dict[str, Any], Job], Awaitable[None]]

HANDLERS: dict[str, JobHandler] = {}

# Módulos que registram handlers (importados pelo worker na inicialização).
HANDLER_MODULES = [
    "app.jobs.system",
    "app.email.jobs",
    "app.modules.users.jobs",
    "app.modules.essays.jobs",
    "app.modules.contests.jobs",
]


def job_handler(queue: str) -> Callable[[JobHandler], JobHandler]:
    def decorator(fn: JobHandler) -> JobHandler:
        if queue in HANDLERS and HANDLERS[queue] is not fn:
            raise RuntimeError(f"Handler duplicado para a fila {queue!r}")
        HANDLERS[queue] = fn
        return fn

    return decorator


def load_handlers() -> dict[str, JobHandler]:
    for module in HANDLER_MODULES:
        importlib.import_module(module)
    return HANDLERS
