from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.rate_limit import limiter
from app.modules.auth import service
from app.modules.auth.cookies import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from app.modules.auth.schemas import (
    EmailIn,
    LoginIn,
    RegisterIn,
    ResetPasswordIn,
    TokenIn,
    TokenOut,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(response: Response, result: service.Session) -> TokenOut:
    set_refresh_cookie(response, result.refresh_token)
    return TokenOut(access_token=result.access_token, expires_in=result.expires_in)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    response: Response,
    data: RegisterIn,
    session: AsyncSession = Depends(get_session),
):
    """Cria a conta, envia o e-mail de verificação e já inicia a sessão."""
    result = await service.register(session, data, request.headers.get("user-agent"))
    return _token_response(response, result)


@router.post("/login", response_model=TokenOut)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    data: LoginIn,
    session: AsyncSession = Depends(get_session),
):
    result = await service.login(
        session, data.email, data.password, request.headers.get("user-agent")
    )
    return _token_response(response, result)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    result = await service.refresh(session, refresh_token, request.headers.get("user-agent"))
    return _token_response(response, result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    await service.logout(session, refresh_token)
    clear_refresh_cookie(response)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/hour")
async def verify_email(
    request: Request, data: TokenIn, session: AsyncSession = Depends(get_session)
):
    await service.verify_email(session, data.token)


@router.post("/resend-verification", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await service.resend_verification(session, user)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/hour")
async def forgot_password(
    request: Request, data: EmailIn, session: AsyncSession = Depends(get_session)
):
    """Sempre 204: não revela se o e-mail está cadastrado."""
    await service.forgot_password(session, data.email)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/hour")
async def reset_password(
    request: Request, data: ResetPasswordIn, session: AsyncSession = Depends(get_session)
):
    """Troca a senha e encerra todas as sessões abertas."""
    await service.reset_password(session, data.token, data.new_password)
