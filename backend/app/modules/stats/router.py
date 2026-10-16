from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.modules.stats import service
from app.modules.stats.schemas import DashboardOut
from app.modules.users.models import User

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Blocos de hoje, última redação, acerto da semana e sequência de dias estudando."""
    return await service.dashboard(session, user)
