"""Configuração de IA por tarefa: provedor, modelo, esforço e chave.

O painel admin grava em `app_settings.ai_tasks` e em `ai_credentials`; sem
nada lá, vale o `.env` (AI_DRIVER, ANTHROPIC_MODEL_*, *_API_KEY).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import TASKS
from app.ai.models import AICredential
from app.ai.types import AIConfigError, TaskConfig
from app.core.config import get_settings
from app.core.crypto import SecretUnavailableError, decrypt
from app.modules.system.settings import get_setting


def env_task(task: str) -> dict:
    """Configuração da tarefa vinda do .env (usada quando o painel não definiu)."""
    s = get_settings()
    if s.ai_driver == "fake":
        return {"provider": "fake", "model": "fake", "effort": None}
    if task == "grading":
        return {
            "provider": "anthropic",
            "model": s.anthropic_model_grading,
            "effort": s.anthropic_effort_grading,
        }
    return {
        "provider": "anthropic",
        "model": s.anthropic_model_transcription,
        "effort": s.anthropic_effort_transcription,
    }


async def task_settings(session: AsyncSession, task: str) -> dict:
    if task not in TASKS:
        raise ValueError(task)
    stored = (await get_setting(session, "ai_tasks")).get(task)
    return {**env_task(task), **stored} if stored else env_task(task)


def env_key(provider: str) -> str:
    s = get_settings()
    return {
        "anthropic": s.anthropic_api_key,
        "openai": s.openai_api_key,
        "google": s.google_api_key,
    }.get(provider, "")


async def get_api_key(session: AsyncSession, provider: str) -> str:
    """Chave do painel (criptografada) ou, se não houver, a do .env."""
    if provider == "fake":
        return ""
    cred = await session.get(AICredential, provider)
    if cred is not None:
        try:
            return decrypt(cred.encrypted_key)
        except SecretUnavailableError as exc:
            raise AIConfigError(
                f"A chave da {provider} salva no painel não pode ser lida ({exc}). "
                "Cadastre-a de novo em Admin → IA."
            ) from exc
    return env_key(provider)


async def resolve_task(
    session: AsyncSession, task: str, *, provider: str | None = None, model: str | None = None
) -> TaskConfig:
    cfg = await task_settings(session, task)
    if provider:
        cfg = {"provider": provider, "model": model or cfg["model"], "effort": None}
    elif model:
        cfg["model"] = model
    return TaskConfig(
        provider=cfg["provider"],
        model=cfg["model"],
        effort=cfg.get("effort") or None,
        api_key=await get_api_key(session, cfg["provider"]),
    )
