"""Envio de e-mails. Sempre chamado pelo job `email.send`, nunca direto de um endpoint."""

import asyncio
import logging

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    pass


def _send_resend(to: str, subject: str, html: str) -> str:
    settings = get_settings()
    resend.api_key = settings.resend_api_key
    result = resend.Emails.send(
        {"from": settings.email_from, "to": [to], "subject": subject, "html": html}
    )
    provider_id = result.get("id") if isinstance(result, dict) else getattr(result, "id", None)
    if not provider_id:
        raise EmailSendError(f"Resposta inesperada do Resend: {result!r}")
    return provider_id


async def send(to: str, subject: str, html: str) -> str | None:
    """Envia e devolve o id do provedor (None no driver `console`)."""
    settings = get_settings()
    if settings.email_driver == "console":
        logger.info(
            "email_console", extra={"extra_fields": {"to": to, "subject": subject, "html": html}}
        )
        return None
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY não configurada")
    return await asyncio.to_thread(_send_resend, to, subject, html)
