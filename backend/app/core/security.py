"""Senhas (argon2), JWT de acesso e tokens opacos (só o hash vai para o banco)."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

ALGORITHM = "HS256"
_hasher = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---- senhas -----------------------------------------------------------------


def hash_password(password: str) -> str:
    return _hasher.hash(password)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def verify_password(password: str, password_hash: str | None) -> tuple[bool, bool]:
    """Retorna (válida, precisa_rehash). Sem hash, verifica contra um dummy
    para o tempo de resposta não revelar se o e-mail existe."""
    try:
        _hasher.verify(password_hash or _dummy_hash(), password)
    except (VerificationError, InvalidHashError):
        return False, False
    if password_hash is None:
        return False, False
    return True, _hasher.check_needs_rehash(password_hash)


# ---- tokens opacos (refresh, verificação de e-mail, reset de senha) ---------


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


# ---- JWT --------------------------------------------------------------------


class InvalidTokenError(Exception):
    pass


def _encode(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, get_settings().jwt_secret, algorithm=ALGORITHM)


def _decode(token: str, typ: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if claims.get("typ") != typ:
        raise InvalidTokenError("tipo de token incorreto")
    return claims


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    ttl = timedelta(minutes=get_settings().access_token_ttl_minutes)
    now = utcnow()
    token = _encode(
        {"sub": str(user_id), "role": role, "typ": "access", "iat": now, "exp": now + ttl}
    )
    return token, int(ttl.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode(token, "access")


def create_unsubscribe_token(user_id: uuid.UUID) -> str:
    """Token do link de descadastro dos lembretes (sem expiração)."""
    return _encode({"sub": str(user_id), "typ": "unsubscribe"})


def decode_unsubscribe_token(token: str) -> uuid.UUID:
    claims = _decode(token, "unsubscribe")
    try:
        return uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("sub inválido") from exc
