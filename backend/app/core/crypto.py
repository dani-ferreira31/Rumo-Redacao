"""Criptografia simétrica (Fernet) para segredos guardados no banco, como chaves de API."""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import AppError


class SecretUnavailableError(Exception):
    """O segredo existe, mas não dá para abrir (chave de criptografia ausente ou trocada)."""


def _fernet() -> Fernet | None:
    key = get_settings().settings_encryption_key
    return Fernet(key.encode()) if key else None


def encryption_configured() -> bool:
    return _fernet() is not None


def encrypt(value: str) -> bytes:
    f = _fernet()
    if f is None:
        raise AppError(
            "encryption_key_missing",
            "Configure SETTINGS_ENCRYPTION_KEY no .env do servidor para salvar chaves de API.",
            503,
        )
    return f.encrypt(value.encode())


def decrypt(token: bytes) -> str:
    f = _fernet()
    if f is None:
        raise SecretUnavailableError("SETTINGS_ENCRYPTION_KEY não configurada")
    try:
        return f.decrypt(token).decode()
    except InvalidToken as exc:
        raise SecretUnavailableError(
            "SETTINGS_ENCRYPTION_KEY diferente da usada ao salvar"
        ) from exc


def hint(secret: str) -> str:
    """Mostra só o começo e o fim: `sk-ant…a1b2`."""
    secret = secret.strip()
    if len(secret) <= 10:
        return "…" + secret[-2:]
    return f"{secret[:6]}…{secret[-4:]}"
