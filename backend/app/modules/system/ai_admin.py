"""Painel admin → IA: chaves (só escrita), modelo por tarefa, preços e calibrações."""

import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import DEFAULT_PRICING, PROVIDERS, TASKS, find_price, pricing_table
from app.ai.client import get_ai_client
from app.ai.config import env_key, env_task, get_api_key, task_settings
from app.ai.models import AICredential, AIUsage
from app.core.config import get_settings
from app.core.crypto import encrypt, encryption_configured, hint
from app.core.errors import AppError
from app.core.security import verify_password
from app.modules.system.settings import get_setting, log_event, set_setting
from app.modules.users.models import User

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


# ---- schemas ---------------------------------------------------------------------


class ProviderOut(BaseModel):
    id: str
    label: str
    efforts: list[str]
    key_url: str | None
    # "panel" = cadastrada no painel; "env" = só no .env do servidor; None = sem chave
    key_source: str | None
    key_hint: str | None
    last_test_at: datetime | None
    last_test_ok: bool | None
    last_test_error: str | None


class ProvidersOut(BaseModel):
    providers: list[ProviderOut]
    encryption_configured: bool


class KeyIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=500)
    password: str = Field(min_length=1, max_length=200)


class ModelOut(BaseModel):
    id: str
    name: str | None = None


class TestOut(BaseModel):
    ok: bool
    error: str | None = None
    models: list[ModelOut] = []


class TaskOut(BaseModel):
    task: str
    label: str
    hint: str
    provider: str
    model: str
    effort: str | None
    source: str  # "panel" | "env"


class TaskIn(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=200)
    effort: str | None = None


class PriceRow(BaseModel):
    model: str
    input: float | None = None
    output: float | None = None
    cache_read: float | None = None
    cache_write: float | None = None
    source: str  # "default" | "panel" | "missing"


class PricesIn(BaseModel):
    prices: list[PriceRow]


class Calibration(BaseModel):
    created_at: datetime
    provider: str
    model: str
    prompt_version: str
    n: int
    ok: int
    cost_usd: float
    total_qwk: float | None
    total_within: float | None
    total_mae: float | None
    report: str


# ---- provedores e chaves ---------------------------------------------------------


def available_providers() -> list[str]:
    names = ["anthropic", "openai", "google"]
    # o simulado só aparece no modo de desenvolvimento (AI_DRIVER=fake)
    if get_settings().ai_driver == "fake":
        names.append("fake")
    return names


async def providers(session: AsyncSession) -> ProvidersOut:
    creds = {c.provider: c for c in await session.scalars(select(AICredential))}
    out = []
    for name in available_providers():
        meta = PROVIDERS[name]
        cred = creds.get(name)
        source = "panel" if cred else ("env" if env_key(name) else None)
        out.append(
            ProviderOut(
                id=name,
                label=meta["label"],
                efforts=meta["efforts"],
                key_url=meta["key_url"],
                key_source=None if name == "fake" else source,
                key_hint=cred.key_hint
                if cred
                else (hint(env_key(name)) if env_key(name) else None),
                last_test_at=cred.last_test_at if cred else None,
                last_test_ok=cred.last_test_ok if cred else None,
                last_test_error=cred.last_test_error if cred else None,
            )
        )
    return ProvidersOut(providers=out, encryption_configured=encryption_configured())


def _check_provider(name: str, allow_fake: bool = False) -> None:
    valid = available_providers() if allow_fake else ["anthropic", "openai", "google"]
    if name not in valid:
        raise AppError("unknown_provider", "Provedor de IA desconhecido.", 404)


async def save_key(
    session: AsyncSession, admin: User, provider: str, api_key: str, password: str
) -> None:
    _check_provider(provider)
    ok, _ = verify_password(password, admin.password_hash)
    if not ok:
        raise AppError("invalid_password", "Senha incorreta.", 403)
    api_key = api_key.strip()
    stmt = insert(AICredential).values(
        provider=provider, encrypted_key=encrypt(api_key), key_hint=hint(api_key)
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[AICredential.provider],
        set_={
            "encrypted_key": stmt.excluded.encrypted_key,
            "key_hint": stmt.excluded.key_hint,
            "last_test_at": None,
            "last_test_ok": None,
            "last_test_error": None,
            "updated_at": datetime.now(UTC),
        },
    )
    await session.execute(stmt)
    log_event(session, "ai", f"Chave da {provider} cadastrada ({hint(api_key)})")
    await session.commit()


async def delete_key(session: AsyncSession, provider: str) -> None:
    _check_provider(provider)
    cred = await session.get(AICredential, provider)
    if cred is not None:
        await session.delete(cred)
        log_event(session, "ai", f"Chave da {provider} removida do painel")
        await session.commit()


def _safe_error(exc: Exception, secret: str) -> str:
    message = f"{type(exc).__name__}: {exc}"[:400]
    return message.replace(secret, "[chave]") if secret else message


async def test_provider(session: AsyncSession, provider: str) -> TestOut:
    """Lista os modelos do provedor: confirma a chave e alimenta a escolha de modelo."""
    _check_provider(provider, allow_fake=True)
    key = ""
    try:
        key = await get_api_key(session, provider)
        models = await get_ai_client().list_models(provider, key)
        result = TestOut(ok=True, models=[ModelOut(id=m.id, name=m.name) for m in models])
    except Exception as exc:
        logger.warning("ai_provider_test_failed", extra={"extra_fields": {"provider": provider}})
        result = TestOut(ok=False, error=_safe_error(exc, key))
    cred = await session.get(AICredential, provider) if provider != "fake" else None
    if cred is not None:
        cred.last_test_at = datetime.now(UTC)
        cred.last_test_ok = result.ok
        cred.last_test_error = result.error
        await session.commit()
    return result


# ---- tarefas ---------------------------------------------------------------------


async def tasks(session: AsyncSession) -> list[TaskOut]:
    stored = await get_setting(session, "ai_tasks")
    out = []
    for task, meta in TASKS.items():
        cfg = await task_settings(session, task)
        out.append(
            TaskOut(
                task=task,
                label=meta["label"],
                hint=meta["hint"],
                provider=cfg["provider"],
                model=cfg["model"],
                effort=cfg.get("effort"),
                source="panel" if task in stored else "env",
            )
        )
    return out


async def set_task(session: AsyncSession, admin: User, task: str, data: TaskIn) -> None:
    if task not in TASKS:
        raise AppError("unknown_task", "Tarefa desconhecida.", 404)
    _check_provider(data.provider, allow_fake=True)
    efforts = PROVIDERS[data.provider]["efforts"]
    if data.effort and data.effort not in efforts:
        raise AppError(
            "invalid_effort",
            "Esse nível de raciocínio não existe para este provedor.",
            422,
            details={"allowed": efforts},
        )
    before = await task_settings(session, task)
    stored = await get_setting(session, "ai_tasks")
    stored[task] = {
        "provider": data.provider,
        "model": data.model.strip(),
        "effort": data.effort or None,
    }
    await set_setting(session, "ai_tasks", stored, admin.id)
    log_event(
        session,
        "ai",
        f"{TASKS[task]['label']}: {before['provider']}/{before['model']} → "
        f"{data.provider}/{data.model.strip()}",
    )
    await session.commit()


async def reset_task(session: AsyncSession, admin: User, task: str) -> None:
    stored = await get_setting(session, "ai_tasks")
    if stored.pop(task, None) is not None:
        await set_setting(session, "ai_tasks", stored, admin.id)
        env = env_task(task)
        log_event(
            session,
            "ai",
            f"{TASKS[task]['label']}: voltou ao padrão do servidor "
            f"({env['provider']}/{env['model']})",
        )
        await session.commit()


# ---- preços ----------------------------------------------------------------------


async def prices(session: AsyncSession) -> list[PriceRow]:
    overrides = await get_setting(session, "ai_pricing")
    table = pricing_table(overrides)
    used = set(await session.scalars(select(AIUsage.model).distinct()))
    configured = {t["model"] for t in (await get_setting(session, "ai_tasks")).values()}
    names = (set(table) | used | configured) - {"fake"}
    rows = []
    for model in sorted(names):
        price = find_price(table, model)
        if price is None:
            rows.append(PriceRow(model=model, source="missing"))
            continue
        source = (
            "panel" if model in overrides else ("default" if model in DEFAULT_PRICING else "panel")
        )
        rows.append(
            PriceRow(
                model=model,
                input=float(price[0]),
                output=float(price[1]),
                cache_read=float(price[2]),
                cache_write=float(price[3]),
                source=source,
            )
        )
    return rows


async def set_prices(session: AsyncSession, admin: User, data: PricesIn) -> None:
    overrides = {}
    for row in data.prices:
        if row.input is None or row.output is None:
            continue
        default = DEFAULT_PRICING.get(row.model)
        values = (row.input, row.output, row.cache_read or 0, row.cache_write or 0)
        if default and tuple(Decimal(str(v)) for v in values) == default:
            continue  # igual ao padrão: não precisa guardar
        if min(values) < 0:
            raise AppError("invalid_price", "Preços não podem ser negativos.", 422)
        fields = ("input", "output", "cache_read", "cache_write")
        overrides[row.model] = dict(zip(fields, values, strict=True))
    await set_setting(session, "ai_pricing", overrides, admin.id)
    log_event(session, "ai", "Tabela de preços de IA atualizada")
    await session.commit()


# ---- calibrações -----------------------------------------------------------------


def calibrations(directory: Path = REPORTS_DIR) -> list[Calibration]:
    """Último relatório de cada provedor+modelo (os .json gerados por eval_grading)."""
    latest: dict[tuple[str, str], Calibration] = {}
    for path in sorted(directory.glob("eval_*.json")) if directory.is_dir() else []:
        try:
            data = json.loads(path.read_text("utf-8"))
            total = data.get("total") or {}
            item = Calibration(
                created_at=data["created_at"],
                provider=data["provider"],
                model=data["model"],
                prompt_version=data["prompt_version"],
                n=data["n"],
                ok=data["ok"],
                cost_usd=data["cost_usd"],
                total_qwk=total.get("qwk"),
                total_within=total.get("within"),
                total_mae=total.get("mae"),
                report=data["report"],
            )
        except (OSError, ValueError, KeyError):
            continue
        key = (item.provider, item.model)
        if key not in latest or item.created_at > latest[key].created_at:
            latest[key] = item
    return sorted(latest.values(), key=lambda c: c.created_at, reverse=True)
