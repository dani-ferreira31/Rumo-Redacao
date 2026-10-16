from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.rate_limit import limiter
from app.modules.invites import service
from app.modules.invites.schemas import InvitePublic

router = APIRouter(prefix="/invites", tags=["auth"])


@router.get("/{code}", response_model=InvitePublic)
@limiter.limit("30/minute")
async def check_invite(request: Request, code: str, session: AsyncSession = Depends(get_session)):
    """Público: a tela de cadastro confere o convite e mostra se é de aluno ou professor."""
    return await service.public_info(session, code)
