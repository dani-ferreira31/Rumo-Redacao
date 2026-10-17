"""Quem pode usar a plataforma: convidados e cortesias sempre; os demais, com assinatura em dia."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.security import utcnow
from app.modules.system.settings import get_setting
from app.modules.users.models import User


async def billing(session: AsyncSession) -> dict:
    return await get_setting(session, "billing")


def access_ok(user: User, billing_enabled: bool, now: datetime | None = None) -> bool:
    if not billing_enabled or user.free_access or user.role != UserRole.student:
        return True
    return user.paid_until is not None and user.paid_until > (now or utcnow())


async def has_access(session: AsyncSession, user: User) -> bool:
    return access_ok(user, bool((await billing(session)).get("enabled")))
