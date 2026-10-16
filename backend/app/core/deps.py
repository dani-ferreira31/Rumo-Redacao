import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.enums import UserRole
from app.core.errors import AppError
from app.core.security import InvalidTokenError, decode_access_token
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)
_WWW_AUTH = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None:
        raise AppError("not_authenticated", "Faça login para continuar.", 401, headers=_WWW_AUTH)
    try:
        claims = decode_access_token(creds.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise AppError(
            "invalid_access_token", "Sessão expirada. Faça login novamente.", 401, headers=_WWW_AUTH
        ) from exc
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(
            "invalid_access_token", "Sessão expirada. Faça login novamente.", 401, headers=_WWW_AUTH
        )
    if user.disabled_at is not None:
        raise AppError(
            "account_disabled",
            "Esta conta foi desativada. Fale com o administrador.",
            401,
            headers=_WWW_AUTH,
        )
    return user


async def require_verified_user(user: User = Depends(get_current_user)) -> User:
    if user.email_verified_at is None:
        raise AppError("email_not_verified", "Confirme seu e-mail para usar este recurso.", 403)
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise AppError("forbidden", "Você não tem permissão para esta ação.", 403)
    return user


async def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.teacher, UserRole.admin):
        raise AppError("forbidden", "Área restrita a professores.", 403)
    return user


def require_feature(name: str):
    """Bloqueia a rota quando o módulo está desligado no painel (o admin sempre passa)."""
    from app.modules.system.settings import FEATURES, feature_enabled

    async def dependency(
        user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
    ) -> User:
        if user.role != UserRole.admin and not await feature_enabled(session, name):
            raise AppError(
                "feature_disabled",
                f"{FEATURES[name]} está temporariamente indisponível.",
                503,
                details={"feature": name},
            )
        return user

    return dependency
