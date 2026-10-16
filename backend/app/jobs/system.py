"""Handlers de sistema (diagnóstico da fila)."""

import logging

from app.jobs.registry import job_handler

logger = logging.getLogger(__name__)


@job_handler("system.ping")
async def ping(session, payload, job) -> None:
    logger.info("pong", extra={"extra_fields": {"payload": payload}})
