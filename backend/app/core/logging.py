"""Logging estruturado em JSON com contexto (request_id, job_id, essay_id)."""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

log_context: ContextVar[dict | None] = ContextVar("log_context", default=None)


def bind_log_context(**values) -> None:
    current = dict(log_context.get() or {})
    current.update({k: v for k, v in values.items() if v is not None})
    log_context.set(current)


def clear_log_context() -> None:
    log_context.set({})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **(log_context.get() or {}),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            data.update(extra)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        # LGPD: a saída dos containers também não leva e-mail, token, senha etc.
        from app.core.applog import MAX_TRACE, scrub

        return json.dumps(scrub(data, limit=MAX_TRACE), ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
    # o log de acesso do uvicorn é substituído pelo middleware de request
    logging.getLogger("uvicorn.access").disabled = True
