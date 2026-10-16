import uuid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_unsubscribe_token
from app.email.models import EmailLog
from app.jobs.queue import enqueue

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)


def render(template: str, context: dict[str, Any]) -> str:
    settings = get_settings()
    return _env.get_template(template).render(app_url=settings.app_url, **context)


def unsubscribe_url(user_id: uuid.UUID) -> str:
    return f"{get_settings().app_url}/descadastrar?token={create_unsubscribe_token(user_id)}"


async def queue_email(
    session: AsyncSession,
    *,
    to: str,
    type: str,
    subject: str,
    template: str,
    context: dict[str, Any],
    user_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
) -> int | None:
    """Registra o e-mail em `email_logs` e enfileira o envio.

    Com `dedupe_key`, um segundo pedido igual é ignorado (devolve None): o log é
    inserido antes do envio com ON CONFLICT DO NOTHING.
    """
    html = render(template, {"subject": subject, **context})
    stmt = (
        insert(EmailLog)
        .values(user_id=user_id, type=type, to_email=to, dedupe_key=dedupe_key)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(EmailLog.id)
    )
    log_id = (await session.execute(stmt)).scalar_one_or_none()
    if log_id is None:
        return None
    await enqueue(
        session,
        "email.send",
        {"email_log_id": log_id, "to": to, "subject": subject, "html": html},
    )
    return log_id
