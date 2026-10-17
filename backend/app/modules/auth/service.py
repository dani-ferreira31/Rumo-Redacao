"""Regras de autenticação: cadastro, login, refresh com rotação e tokens de e-mail."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import EmailTokenPurpose, UserRole
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    utcnow,
    verify_password,
)
from app.email.service import queue_email
from app.modules.auth.models import EmailToken, RefreshToken
from app.modules.auth.schemas import RegisterIn
from app.modules.invites.service import claim as claim_invite
from app.modules.payments.service import public_billing
from app.modules.system.settings import feature_enabled
from app.modules.users.models import User

logger = logging.getLogger(__name__)

VERIFY_EMAIL_TTL = timedelta(hours=24)
RESET_PASSWORD_TTL = timedelta(hours=1)
# Duas abas (ou o StrictMode do React) podem renovar a sessão ao mesmo tempo com o
# mesmo token. Dentro desta janela, o reuso de um token recém-rotacionado não é
# tratado como roubo.
REFRESH_REUSE_GRACE = timedelta(seconds=20)
ADULT_AGE = 18


@dataclass
class Session:
    access_token: str
    expires_in: int
    refresh_token: str  # valor em claro: só vai para o cookie
    refresh_token_row: RefreshToken


def _invalid_credentials() -> AppError:
    return AppError("invalid_credentials", "E-mail ou senha incorretos.", 401)


def account_disabled() -> AppError:
    return AppError("account_disabled", "Esta conta foi desativada. Fale com o administrador.", 401)


def _age_on(birth: date, today: date) -> int:
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---- sessões ----------------------------------------------------------------


async def _start_session(session: AsyncSession, user: User, user_agent: str | None) -> Session:
    raw, token_hash = generate_token()
    row = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=utcnow() + timedelta(days=get_settings().refresh_token_ttl_days),
        user_agent=(user_agent or "")[:300] or None,
    )
    session.add(row)
    await session.flush()
    access, expires_in = create_access_token(user.id, user.role)
    return Session(access, expires_in, raw, row)


async def register(session: AsyncSession, data: RegisterIn, user_agent: str | None) -> Session:
    if not await feature_enabled(session, "registration"):
        raise AppError(
            "registration_closed", "Novos cadastros estão temporariamente fechados.", 503
        )
    email = normalize_email(data.email)
    is_minor = _age_on(data.birth_date, date.today()) < ADULT_AGE
    if is_minor and not data.guardian_consent:
        raise AppError(
            "guardian_consent_required",
            "Menores de 18 anos precisam do consentimento do responsável.",
            422,
        )
    # Com convite: papel do convite e acesso livre. Sem convite: aluno, e só se o
    # cadastro pago estiver aberto (a conta entra, mas precisa assinar).
    # O convite vem antes: sem um válido, não dá para descobrir quais e-mails já existem.
    if data.invite_code:
        invite = await claim_invite(session, data.invite_code)
    else:
        invite = None
        if not (await public_billing(session)).enabled:
            raise AppError(
                "invite_required",
                "O cadastro é feito por convite. Peça o link a quem administra a plataforma.",
                403,
            )
    if await session.scalar(select(User.id).where(User.email == email)):
        raise AppError("email_already_registered", "Este e-mail já está cadastrado.", 409)

    user = User(
        name=data.name,
        email=email,
        password_hash=hash_password(data.password),
        role=invite.role if invite else UserRole.student,
        invite_id=invite.id if invite else None,
        free_access=invite is not None,
        birth_date=data.birth_date,
        guardian_consent_at=utcnow() if is_minor else None,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:  # cadastro simultâneo com o mesmo e-mail
        await session.rollback()
        raise AppError("email_already_registered", "Este e-mail já está cadastrado.", 409) from exc

    await send_verification_email(session, user)
    result = await _start_session(session, user, user_agent)
    await session.commit()
    return result


async def login(
    session: AsyncSession, email: str, password: str, user_agent: str | None
) -> Session:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    valid, needs_rehash = verify_password(password, user.password_hash if user else None)
    if not valid or user is None:
        raise _invalid_credentials()
    if user.disabled_at is not None:
        raise account_disabled()
    if needs_rehash:
        user.password_hash = hash_password(password)
    result = await _start_session(session, user, user_agent)
    await session.commit()
    return result


async def _revoke_all(session: AsyncSession, user_id) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def _refresh_error(code: str = "invalid_refresh_token") -> AppError:
    return AppError(code, "Sua sessão expirou. Faça login novamente.", 401)


async def refresh(session: AsyncSession, raw: str | None, user_agent: str | None) -> Session:
    if not raw:
        raise _refresh_error("refresh_token_missing")
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)).with_for_update()
    )
    if token is None:
        raise _refresh_error()

    now = utcnow()
    if token.revoked_at is not None:
        in_grace = token.replaced_by is not None and now - token.revoked_at <= REFRESH_REUSE_GRACE
        if not in_grace:
            # Reuso de token já rotacionado: possível roubo. Derruba todas as sessões.
            await _revoke_all(session, token.user_id)
            await session.commit()
            logger.warning(
                "refresh_token_reused", extra={"extra_fields": {"user_id": str(token.user_id)}}
            )
            raise _refresh_error("refresh_token_reused")
    elif token.expires_at <= now:
        raise _refresh_error("refresh_token_expired")

    user = await session.get(User, token.user_id)
    if user is None:
        raise _refresh_error()
    if user.disabled_at is not None:
        raise account_disabled()

    result = await _start_session(session, user, user_agent)
    if token.revoked_at is None:
        token.revoked_at = now
        token.replaced_by = result.refresh_token_row.id
    await session.commit()
    return result


async def logout(session: AsyncSession, raw: str | None) -> None:
    if not raw:
        return
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await session.commit()


# ---- tokens de e-mail -------------------------------------------------------


async def _issue_email_token(
    session: AsyncSession, user: User, purpose: EmailTokenPurpose, ttl: timedelta
) -> str:
    """Cria um token novo e invalida (apaga) os anteriores ainda não usados."""
    await session.execute(
        delete(EmailToken).where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
    )
    raw, token_hash = generate_token()
    session.add(
        EmailToken(
            user_id=user.id, purpose=purpose, token_hash=token_hash, expires_at=utcnow() + ttl
        )
    )
    return raw


async def _consume_email_token(
    session: AsyncSession, raw: str, purpose: EmailTokenPurpose
) -> EmailToken:
    token = await session.scalar(
        select(EmailToken).where(EmailToken.token_hash == hash_token(raw)).with_for_update()
    )
    if token is None or token.purpose != purpose:
        raise AppError("invalid_token", "Link inválido. Peça um novo.", 400)
    if token.used_at is not None:
        raise AppError("token_already_used", "Este link já foi usado.", 400)
    if token.expires_at <= utcnow():
        raise AppError("token_expired", "Este link expirou. Peça um novo.", 400)
    token.used_at = utcnow()
    return token


async def send_verification_email(session: AsyncSession, user: User) -> None:
    raw = await _issue_email_token(session, user, EmailTokenPurpose.verify_email, VERIFY_EMAIL_TTL)
    await queue_email(
        session,
        user_id=user.id,
        to=user.email,
        type="verify_email",
        subject="Confirme seu e-mail no Rumo1000",
        template="verify_email.html",
        context={"name": user.name, "url": f"{get_settings().app_url}/verificar-email?token={raw}"},
    )


async def resend_verification(session: AsyncSession, user: User) -> None:
    if user.email_verified_at is not None:
        raise AppError("email_already_verified", "Seu e-mail já está confirmado.", 409)
    await send_verification_email(session, user)
    await session.commit()


async def verify_email(session: AsyncSession, raw: str) -> None:
    token = await _consume_email_token(session, raw, EmailTokenPurpose.verify_email)
    user = await session.get(User, token.user_id)
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await session.commit()


async def forgot_password(session: AsyncSession, email: str) -> None:
    """Não revela se o e-mail existe: quem chama sempre responde 204."""
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.disabled_at is not None:
        return
    raw = await _issue_email_token(
        session, user, EmailTokenPurpose.reset_password, RESET_PASSWORD_TTL
    )
    await queue_email(
        session,
        user_id=user.id,
        to=user.email,
        type="reset_password",
        subject="Redefinição de senha do Rumo1000",
        template="reset_password.html",
        context={"name": user.name, "url": f"{get_settings().app_url}/redefinir-senha?token={raw}"},
    )
    await session.commit()


async def reset_password(session: AsyncSession, raw: str, new_password: str) -> None:
    token = await _consume_email_token(session, raw, EmailTokenPurpose.reset_password)
    user = await session.get(User, token.user_id)
    user.password_hash = hash_password(new_password)
    # Quem abriu o link provou que controla o e-mail.
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await _revoke_all(session, user.id)
    await session.commit()
