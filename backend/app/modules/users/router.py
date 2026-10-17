from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.modules.auth.cookies import clear_refresh_cookie
from app.modules.payments.access import has_access
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import UnsubscribeOut, UserOut, UserUpdate

router = APIRouter(prefix="/me", tags=["me"])


async def _me(session: AsyncSession, user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.access_active = await has_access(session, user)
    return out


@router.get("", response_model=UserOut)
async def get_me(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await _me(session, user)


@router.patch("", response_model=UserOut)
async def update_me(
    data: UserUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _me(session, await service.update_user(session, user, data))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.delete_account(session, user)
    clear_refresh_cookie(response)


@router.get("/unsubscribe", response_model=UnsubscribeOut)
async def unsubscribe(token: str = Query(...), session: AsyncSession = Depends(get_session)):
    """Público: desliga os lembretes por e-mail (link presente nos e-mails de lembrete)."""
    await service.unsubscribe(session, token)
    return UnsubscribeOut(email_reminders_enabled=False)
