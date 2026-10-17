import uuid

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.errors import AppError, NotFoundError
from app.core.security import InvalidTokenError, decode_unsubscribe_token, utcnow
from app.jobs.queue import enqueue
from app.modules.auth.models import RefreshToken
from app.modules.system.settings import log_event
from app.modules.users.models import User
from app.modules.users.schemas import AdminUserUpdate, UserUpdate


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


# ---- admin: gestão de contas -----------------------------------------------------

ROLE_LABEL = {UserRole.student: "aluno", UserRole.teacher: "professor", UserRole.admin: "admin"}


async def admin_list_users(
    session: AsyncSession,
    q: str | None,
    role: UserRole | None,
    disabled: bool | None,
    limit: int,
    offset: int,
) -> tuple[list[User], int]:
    stmt = select(User)
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(term), User.email.ilike(term)))
    if role is not None:
        stmt = stmt.where(User.role == role)
    if disabled is not None:
        stmt = stmt.where(User.disabled_at.is_not(None) if disabled else User.disabled_at.is_(None))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = await session.scalars(
        stmt.order_by(User.created_at.desc(), User.id).offset(offset).limit(limit)
    )
    return list(rows), total or 0


async def admin_update_user(
    session: AsyncSession, admin: User, user_id: uuid.UUID, data: AdminUserUpdate
) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado.")
    if user.id == admin.id or user.role == UserRole.admin:
        raise AppError(
            "cannot_change_admin", "Contas de administrador não podem ser alteradas aqui.", 409
        )
    if data.role is not None and data.role != user.role:
        log_event(
            session, "user", f"Conta mudou de {ROLE_LABEL[user.role]} para {ROLE_LABEL[data.role]}"
        )
        user.role = data.role
    if data.disabled is True and user.disabled_at is None:
        user.disabled_at = utcnow()
        # derruba as sessões abertas: o refresh para de funcionar na hora
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        log_event(session, "user", f"Conta de {ROLE_LABEL[user.role]} desativada")
    elif data.disabled is False and user.disabled_at is not None:
        user.disabled_at = None
        log_event(session, "user", f"Conta de {ROLE_LABEL[user.role]} reativada")
    if data.free_access is not None and data.free_access != user.free_access:
        user.free_access = data.free_access
        word = "liberado sem assinatura" if data.free_access else "voltou a exigir assinatura"
        log_event(session, "user", f"Acesso de {ROLE_LABEL[user.role]} {word}")
    await session.commit()
    await session.refresh(user)
    return user
