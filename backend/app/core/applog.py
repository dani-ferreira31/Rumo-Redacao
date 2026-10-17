"""Registro de avisos e erros no banco (Admin → Logs), com dados pessoais removidos.

LGPD (minimização): antes de gravar, `scrub` tira e-mails, tokens, chaves de API,
CPF e telefones dos textos, e campos com nome, e-mail, senha, texto de redação
ou id de usuário. IP e corpo das requisições nunca são registrados. Os registros
são apagados após `logs.retention_days` (painel), pelo worker.

O handler só guarda em memória; quem grava é `flush_logs`, chamado pela API (a
cada poucos segundos) e pelo worker (tarefa periódica). Se o banco falhar, os
registros pendentes são descartados: o log no stdout continua existindo.
"""

import logging
import re
import sys
import traceback
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log_context

MAX_BUFFER = 1000
MAX_TEXT = 2000
MAX_TRACE = 8000
# bibliotecas barulhentas ou que poderiam ecoar dados de requisição
IGNORED_LOGGERS = ("sqlalchemy", "httpx", "httpcore", "app.core.applog", "multipart")

_SENSITIVE_KEY = re.compile(
    r"pass|senha|token|secret|segredo|key|authorization|cookie|email|e_mail|name|nome|"
    r"birth|cpf|phone|telefone|address|endereco|transcri|statement|answer|user_id|"
    r"(?:^|_)(?:ip|text)(?:$|_)",
    re.I,
)
_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[e-mail]"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "[token]"),
    (re.compile(r"(?i)\bbearer\s+[\w.~+/=-]+"), "Bearer [token]"),
    (re.compile(r"\b(?:APP_USR|TEST)-[\w-]{10,}"), "[chave]"),
    (re.compile(r"\b(?:sk-[\w-]{10,}|sk-ant-[\w-]{10,}|AIza[\w-]{20,})"), "[chave]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    (re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[telefone]"),
]


def scrub_text(value: str, limit: int = MAX_TEXT) -> str:
    for pattern, repl in _PATTERNS:
        value = pattern.sub(repl, value)
    return value[:limit]


def scrub(value: Any, depth: int = 0, limit: int = MAX_TEXT) -> Any:
    """Remove dados pessoais de textos, listas e dicionários (recursivo, com limite)."""
    if depth > 4:
        return "[...]"
    if isinstance(value, dict):
        return {
            str(k): "[removido]" if _SENSITIVE_KEY.search(str(k)) else scrub(v, depth + 1, limit)
            for k, v in list(value.items())[:50]
        }
    if isinstance(value, list | tuple):
        return [scrub(v, depth + 1, limit) for v in list(value)[:50]]
    if isinstance(value, str):
        return scrub_text(value, limit)
    if value is None or isinstance(value, bool | int | float):
        return value
    return scrub_text(str(value), limit)


class DbLogHandler(logging.Handler):
    """Guarda avisos e erros em memória para `flush_logs` gravar no banco."""

    def __init__(self, source: str, level: int = logging.WARNING):
        super().__init__(level)
        self.source = source
        self.buffer: deque[dict[str, Any]] = deque(maxlen=MAX_BUFFER)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith(IGNORED_LOGGERS):
            return
        try:
            details = {**(log_context.get() or {}), **(getattr(record, "extra_fields", None) or {})}
            request_id = details.pop("request_id", None)
            path = details.pop("path", None)
            error = trace = None
            if record.exc_info and record.exc_info[1] is not None:
                exc = record.exc_info[1]
                error = f"{type(exc).__name__}: {exc}"
                trace = "".join(traceback.format_exception(*record.exc_info))
            self.buffer.append(
                {
                    "created_at": datetime.fromtimestamp(record.created, UTC),
                    "level": record.levelname,
                    "source": self.source,
                    "logger": record.name[:200],
                    "event": scrub_text(record.getMessage(), 300),
                    "error": scrub_text(error, 500) if error else None,
                    "traceback": scrub_text(trace, MAX_TRACE) if trace else None,
                    "request_id": str(request_id)[:64] if request_id else None,
                    "path": scrub_text(str(path), 300) if path else None,
                    "details": scrub(details),
                }
            )
        except Exception:  # um log nunca pode derrubar a aplicação
            self.handleError(record)


_handler: DbLogHandler | None = None


def install(source: str) -> DbLogHandler:
    """Liga o registro no banco para este processo ("api" ou "worker")."""
    global _handler
    root = logging.getLogger()
    if _handler is not None:
        root.removeHandler(_handler)
    _handler = DbLogHandler(source)
    root.addHandler(_handler)
    return _handler


def pending() -> int:
    return len(_handler.buffer) if _handler else 0


async def flush_logs(session: AsyncSession) -> int:
    """Grava o que está em memória. Devolve quantos registros foram gravados."""
    from app.modules.system.models import AppLog

    if _handler is None or not _handler.buffer:
        return 0
    rows = []
    while _handler.buffer:
        rows.append(_handler.buffer.popleft())
    try:
        await session.execute(insert(AppLog), rows)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        print(f"app_log_flush_failed: {type(exc).__name__}", file=sys.stderr)
        return 0
    return len(rows)


async def purge_old_logs(session: AsyncSession, retention_days: int) -> int:
    from app.modules.system.models import AppLog

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = await session.execute(delete(AppLog).where(AppLog.created_at < cutoff))
    await session.commit()
    return result.rowcount or 0
