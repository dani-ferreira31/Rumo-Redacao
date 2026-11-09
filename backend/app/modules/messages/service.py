"""Mensagens personalizadas por e-mail: boas-vindas automática na primeira assinatura
aprovada e envio avulso pelo admin para uma conta escolhida em Admin → Usuários."""

import uuid
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.email.service import queue_email
from app.modules.messages.schemas import MessageIn, WelcomeSettings
from app.modules.system.settings import get_setting, log_event, set_setting
from app.modules.users.models import User


def first_name(name: str) -> str:
    return (name or "").strip().split(" ")[0] or "estudante"


def paragraphs(body: str, name: str) -> list[list[str]]:
    """Texto do admin -> parágrafos (linha em branco separa) com {nome} trocado.

    O template escapa o HTML: o texto do admin nunca vira marcação.
    """
    text = body.replace("{nome}", first_name(name)).replace("\r\n", "\n")
    blocks = [b.strip() for b in text.split("\n\n")]
    return [b.split("\n") for b in blocks if b]


async def _queue(
    session: AsyncSession,
    user: User,
    *,
    type: str,
    subject: str,
    body: str,
    dedupe_key: str | None = None,
    delay_minutes: int = 0,
) -> int | None:
    return await queue_email(
        session,
        to=user.email,
        type=type,
        subject=subject.replace("{nome}", first_name(user.name)),
        template="custom_message.html",
        context={
            "paragraphs": paragraphs(body, user.name),
            "url": f"{get_settings().app_url}/painel",
        },
        user_id=user.id,
        dedupe_key=dedupe_key,
        run_after=utcnow() + timedelta(minutes=delay_minutes) if delay_minutes else None,
    )


async def welcome_settings(session: AsyncSession) -> WelcomeSettings:
    return WelcomeSettings(**await get_setting(session, "welcome"))


async def set_welcome_settings(
    session: AsyncSession, admin: User, data: WelcomeSettings
) -> WelcomeSettings:
    await set_setting(session, "welcome", data.model_dump(), admin.id)
    log_event(
        session,
        "settings",
        f"Boas-vindas {'ligada' if data.enabled else 'desligada'} "
        f"(envio {data.delay_minutes} min após o pagamento)",
    )
    await session.commit()
    return data


async def queue_welcome_after_payment(session: AsyncSession, user: User) -> None:
    """Chamado na aprovação de uma assinatura (sem commit). Uma vez por conta."""
    cfg = await welcome_settings(session)
    if not cfg.enabled:
        return
    await _queue(
        session,
        user,
        type="welcome",
        subject=cfg.subject,
        body=cfg.body,
        dedupe_key=f"welcome:{user.id}",
        delay_minutes=cfg.delay_minutes,
    )


async def send_welcome_test(session: AsyncSession, admin: User, data: MessageIn) -> None:
    """Manda o texto (ainda não salvo) para o próprio admin conferir."""
    await _queue(session, admin, type="welcome_test", subject=data.subject, body=data.body)
    await session.commit()


async def send_to_user(
    session: AsyncSession, admin: User, user_id: uuid.UUID, data: MessageIn
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("Conta não encontrada.")
    if user.disabled_at is not None:
        raise AppError("user_disabled", "Esta conta está desativada.", 409)
    await _queue(session, user, type="admin_message", subject=data.subject, body=data.body)
    log_event(session, "email", "Mensagem personalizada enviada a uma conta")  # sem dados pessoais
    await session.commit()
