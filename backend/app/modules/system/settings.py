"""Configurações editáveis pelo painel admin, guardadas em `app_settings`.

Cada chave tem um valor padrão; o que estiver no banco é mesclado por cima.
A leitura tem cache curto por processo, então API e worker passam a usar uma
mudança em poucos segundos, sem reiniciar.
"""

import copy
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.system.models import AppSetting, SystemEvent

CACHE_SECONDS = 10.0

FEATURES = {
    "essays": "Correção de redações",
    "questions_enem": "Questões do ENEM",
    "questions_concursos": "Questões de concursos",
    "planner": "Cronograma de estudos",
    "registration": "Cadastro por convite",
    "email_reminders": "Lembretes por e-mail",
}

DEFAULTS: dict[str, Any] = {
    "features": {name: True for name in FEATURES},
    # ai_budget_usd None = sem teto. O mês segue o fuso de São Paulo.
    # teacher_essays_per_month None = professor sem limite (corrige redações das turmas)
    "limits": {"essays_per_month": 10, "teacher_essays_per_month": None, "ai_budget_usd": None},
    # tarefa -> {"provider", "model", "effort"}; vazio = usa o .env
    "ai_tasks": {},
    # modelo -> {"input", "output", "cache_read", "cache_write"} em US$ por 1M de tokens
    "ai_pricing": {},
    # Cota do plano gratuito (o provedor não informa o saldo: o app conta o próprio uso).
    # model_match casa por trecho do nome do modelo gravado em ai_usage.
    "ai_quotas": [
        {
            "provider": "google",
            "model_match": "flash-lite",
            "rpm": 15,
            "tpm": 250000,
            "rpd": 1000,
        }
    ],
    # Assinatura paga para quem se cadastra sem convite (Mercado Pago). Desligada,
    # o cadastro volta a ser só por convite.
    "billing": {
        "enabled": False,
        "price_brl": 10.0,
        "period_days": 35,
        "donations_enabled": True,
    },
    "worker_heartbeat": None,
}

_cache: dict[str, tuple[float, Any]] = {}


def clear_cache() -> None:
    _cache.clear()


def _merge(default: Any, stored: Any) -> Any:
    if isinstance(default, dict) and isinstance(stored, dict):
        out = copy.deepcopy(default)
        out.update(stored)
        return out
    return copy.deepcopy(default) if stored is None else stored


async def get_setting(session: AsyncSession, key: str) -> Any:
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return copy.deepcopy(cached[1])
    stored = await session.scalar(select(AppSetting.value).where(AppSetting.key == key))
    value = _merge(DEFAULTS.get(key), stored)
    _cache[key] = (time.monotonic() + CACHE_SECONDS, value)
    return copy.deepcopy(value)


async def set_setting(
    session: AsyncSession, key: str, value: Any, user_id: uuid.UUID | None = None
) -> None:
    """Grava (sem commit). Quem chama faz o commit."""
    stmt = insert(AppSetting).values(key=key, value=value, updated_by=user_id)
    stmt = stmt.on_conflict_do_update(
        index_elements=[AppSetting.key],
        set_={"value": stmt.excluded.value, "updated_by": user_id, "updated_at": func.now()},
    )
    await session.execute(stmt)
    _cache.pop(key, None)


async def feature_enabled(session: AsyncSession, name: str) -> bool:
    return bool((await get_setting(session, "features")).get(name, True))


def log_event(session: AsyncSession, kind: str, message: str) -> None:
    """Registra uma ação no log do sistema. Não coloque dados de alunos aqui."""
    session.add(SystemEvent(kind=kind, message=message))
