import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_admin
from app.modules.messages import service
from app.modules.messages.schemas import MessageIn, MessageQueued, WelcomeSettings
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/messages/welcome", response_model=WelcomeSettings)
async def get_welcome(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    """Texto da boas-vindas automática (sem dados de alunos)."""
    return await service.welcome_settings(session)


@router.put("/messages/welcome", response_model=WelcomeSettings)
async def put_welcome(
    data: WelcomeSettings,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await service.set_welcome_settings(session, admin, data)


@router.post(
    "/messages/welcome/test", response_model=MessageQueued, status_code=status.HTTP_202_ACCEPTED
)
async def test_welcome(
    data: MessageIn,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Envia o texto para o e-mail do próprio admin."""
    await service.send_welcome_test(session, admin, data)
    return MessageQueued()


@router.post(
    "/users/{user_id}/message", response_model=MessageQueued, status_code=status.HTTP_202_ACCEPTED
)
async def message_user(
    user_id: uuid.UUID,
    data: MessageIn,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Mensagem personalizada por e-mail para uma conta (escolhida em Admin → Usuários)."""
    await service.send_to_user(session, admin, user_id, data)
    return MessageQueued()
