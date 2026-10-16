"""Convites: o cadastro só acontece por um link válido, que define o papel (aluno ou professor)."""

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.modules.invites.models import Invite
from app.modules.invites.schemas import InviteIn, InviteOut, InvitePublic
from app.modules.system.settings import log_event
from app.modules.users.models import User

ROLE_LABEL = {UserRole.student: "aluno", UserRole.teacher: "professor"}


def invite_url(code: str) -> str:
    return f"{get_settings().app_url}/cadastro?convite={code}"


def invite_status(invite: Invite, now: datetime | None = None) -> str:
    now = now or utcnow()
    if invite.revoked_at is not None:
        return "revoked"
    if invite.expires_at is not None and invite.expires_at <= now:
        return "expired"
    if invite.max_uses is not None and invite.uses >= invite.max_uses:
        return "used_up"
    return "active"


def invite_out(invite: Invite) -> InviteOut:
    return InviteOut(
        id=invite.id,
        code=invite.code,
        url=invite_url(invite.code),
        role=invite.role,
        note=invite.note,
        max_uses=invite.max_uses,
        uses=invite.uses,
        expires_at=invite.expires_at,
        revoked_at=invite.revoked_at,
        created_at=invite.created_at,
        status=invite_status(invite),
    )


def _invalid() -> AppError:
    return AppError(
        "invite_invalid",
        "Este convite não é válido: pode ter expirado, sido revogado ou atingido o limite de usos.",
        403,
    )


async def public_info(session: AsyncSession, code: str) -> InvitePublic:
    invite = await session.scalar(select(Invite).where(Invite.code == code.strip()))
    if invite is None or invite_status(invite) != "active":
        raise _invalid()
    return InvitePublic(role=invite.role, expires_at=invite.expires_at)


async def claim(session: AsyncSession, code: str) -> Invite:
    """Trava o convite e conta mais um uso (sem commit). Quem chama cria o usuário."""
    invite = await session.scalar(
        select(Invite).where(Invite.code == code.strip()).with_for_update()
    )
    if invite is None or invite_status(invite) != "active":
        raise _invalid()
    invite.uses += 1
    return invite


async def list_invites(session: AsyncSession) -> list[InviteOut]:
    rows = await session.scalars(select(Invite).order_by(Invite.created_at.desc()))
    return [invite_out(i) for i in rows]


async def create_invite(session: AsyncSession, admin: User, data: InviteIn) -> InviteOut:
    invite = Invite(
        code=secrets.token_urlsafe(12),
        role=data.role,
        note=(data.note or "").strip() or None,
        max_uses=data.max_uses,
        expires_at=utcnow() + timedelta(days=data.expires_in_days)
        if data.expires_in_days
        else None,
        created_by=admin.id,
    )
    session.add(invite)
    await session.flush()
    log_event(session, "invite", f"Convite de {ROLE_LABEL[data.role]} criado")
    await session.commit()
    await session.refresh(invite)
    return invite_out(invite)


async def revoke_invite(session: AsyncSession, invite_id: uuid.UUID) -> InviteOut:
    invite = await session.get(Invite, invite_id)
    if invite is None:
        raise NotFoundError("Convite não encontrado.")
    if invite.revoked_at is None:
        invite.revoked_at = utcnow()
        log_event(session, "invite", f"Convite de {ROLE_LABEL[invite.role]} revogado")
        await session.commit()
        await session.refresh(invite)
    return invite_out(invite)
