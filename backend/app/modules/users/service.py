import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import InvalidTokenError, decode_unsubscribe_token
from app.jobs.queue import enqueue
from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate


def storage_prefix(user_id: uuid.UUID) -> str:
    return f"users/{user_id}/"


async def update_user(session: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        if field in ("name", "timezone", "email_reminders_enabled") and value is None:
            continue  # campos obrigatórios no banco: null = não alterar
        setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_account(session: AsyncSession, user: User) -> None:
    """Apaga o usuário (cascata no banco) e agenda a limpeza dos arquivos."""
    user_id = user.id
    await session.execute(delete(User).where(User.id == user_id))
    await enqueue(session, "user.purge_storage", {"user_id": str(user_id)})
    await session.commit()


async def unsubscribe(session: AsyncSession, token: str) -> None:
    try:
        user_id = decode_unsubscribe_token(token)
    except InvalidTokenError as exc:
        raise AppError("invalid_token", "Link de descadastro inválido.", 400) from exc
    user = await session.get(User, user_id)
    if user is None:
        raise AppError("invalid_token", "Link de descadastro inválido.", 400)
    user.email_reminders_enabled = False
    await session.commit()
