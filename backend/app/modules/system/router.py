"""Rotas do painel admin (sistema, módulos, limites, IA, custos) e `/features` (pública)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_admin
from app.core.enums import JobStatus
from app.core.errors import AppError
from app.modules.system import ai_admin, logs, quota, service
from app.modules.system.models import SystemEvent
from app.modules.system.schemas import (
    CostReport,
    EventOut,
    FeatureOut,
    FeaturesIn,
    HealthOut,
    JobsOut,
    Limits,
    OverviewOut,
    Period,
)
from app.modules.system.settings import FEATURES, get_setting, log_event, set_setting
from app.modules.users.models import User
from app.storage import LocalStorage, get_storage

router = APIRouter(tags=["system"])
admin = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/features", response_model=dict[str, bool])
async def public_features(session: AsyncSession = Depends(get_session)):
    """Quais módulos estão ligados (o menu do app esconde os desligados)."""
    return await get_setting(session, "features")


# ---- visão geral e sistema -------------------------------------------------------


@admin.get("/overview", response_model=OverviewOut)
async def overview(session: AsyncSession = Depends(get_session)):
    return await service.overview(session)


@admin.get("/system/health", response_model=HealthOut)
async def system_health(
    session: AsyncSession = Depends(get_session), storage: LocalStorage = Depends(get_storage)
):
    return await service.health(session, storage)


@admin.get("/jobs", response_model=JobsOut)
async def list_jobs(
    status_: JobStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    return await service.jobs(session, status_, limit)


@admin.post("/jobs/{job_id}/retry", status_code=status.HTTP_204_NO_CONTENT)
async def retry_job(job_id: int, session: AsyncSession = Depends(get_session)):
    await service.retry_job(session, job_id)


@admin.post("/jobs/{job_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(job_id: int, session: AsyncSession = Depends(get_session)):
    await service.cancel_job(session, job_id)


@admin.get("/events", response_model=list[EventOut])
async def events(
    limit: int = Query(default=50, ge=1, le=200), session: AsyncSession = Depends(get_session)
):
    rows = await session.scalars(
        select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(limit)
    )
    return [EventOut.model_validate(e, from_attributes=True) for e in rows]


# ---- módulos e limites -----------------------------------------------------------


@admin.get("/settings/features", response_model=list[FeatureOut])
async def get_features(session: AsyncSession = Depends(get_session)):
    flags = await get_setting(session, "features")
    return [FeatureOut(name=n, label=label, enabled=flags[n]) for n, label in FEATURES.items()]


@admin.put("/settings/features", response_model=list[FeatureOut])
async def put_features(
    data: FeaturesIn,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    unknown = set(data.features) - set(FEATURES)
    if unknown:
        raise AppError("unknown_feature", "Módulo desconhecido.", 422, {"unknown": sorted(unknown)})
    flags = await get_setting(session, "features")
    for name, enabled in data.features.items():
        if flags[name] != enabled:
            word = "ligado" if enabled else "desligado"
            log_event(session, "feature", f"{FEATURES[name]}: {word}")
        flags[name] = enabled
    await set_setting(session, "features", flags, user.id)
    await session.commit()
    return await get_features(session)


@admin.get("/settings/limits", response_model=Limits)
async def get_limits(session: AsyncSession = Depends(get_session)):
    return Limits(**await get_setting(session, "limits"))


@admin.put("/settings/limits", response_model=Limits)
async def put_limits(
    data: Limits, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    await set_setting(session, "limits", data.model_dump(), user.id)
    per_month = data.essays_per_month or "sem limite"
    teacher = data.teacher_essays_per_month or "sem limite"
    budget = f"US$ {data.ai_budget_usd:.2f}" if data.ai_budget_usd else "sem teto"
    log_event(
        session,
        "limits",
        f"Limites: {per_month} redações/mês por aluno, {teacher} por professor; "
        f"orçamento de IA {budget}",
    )
    await session.commit()
    return data


# ---- custos ----------------------------------------------------------------------


@admin.get("/costs", response_model=CostReport)
async def costs(
    period: Period = Query(default="month"), session: AsyncSession = Depends(get_session)
):
    """Custo de IA por dia, modelo e tarefa. Só agregados, sem dados de alunos."""
    return await service.cost_report(session, period)


# ---- IA --------------------------------------------------------------------------


@admin.get("/ai/providers", response_model=ai_admin.ProvidersOut)
async def ai_providers(session: AsyncSession = Depends(get_session)):
    return await ai_admin.providers(session)


@admin.put("/ai/providers/{provider}/key", status_code=status.HTTP_204_NO_CONTENT)
async def ai_save_key(
    provider: str,
    data: ai_admin.KeyIn,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Salva a chave criptografada. Exige a senha do admin; a chave nunca é devolvida."""
    await ai_admin.save_key(session, user, provider, data.api_key, data.password)


@admin.delete("/ai/providers/{provider}/key", status_code=status.HTTP_204_NO_CONTENT)
async def ai_delete_key(provider: str, session: AsyncSession = Depends(get_session)):
    await ai_admin.delete_key(session, provider)


@admin.post("/ai/providers/{provider}/test", response_model=ai_admin.TestOut)
async def ai_test(provider: str, session: AsyncSession = Depends(get_session)):
    """Testa a chave listando os modelos disponíveis no provedor."""
    return await ai_admin.test_provider(session, provider)


@admin.get("/ai/tasks", response_model=list[ai_admin.TaskOut])
async def ai_tasks(session: AsyncSession = Depends(get_session)):
    return await ai_admin.tasks(session)


@admin.put("/ai/tasks/{task}", response_model=list[ai_admin.TaskOut])
async def ai_set_task(
    task: str,
    data: ai_admin.TaskIn,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await ai_admin.set_task(session, user, task, data)
    return await ai_admin.tasks(session)


@admin.delete("/ai/tasks/{task}", response_model=list[ai_admin.TaskOut])
async def ai_reset_task(
    task: str, user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    await ai_admin.reset_task(session, user, task)
    return await ai_admin.tasks(session)


@admin.get("/ai/prices", response_model=list[ai_admin.PriceRow])
async def ai_prices(session: AsyncSession = Depends(get_session)):
    return await ai_admin.prices(session)


@admin.put("/ai/prices", response_model=list[ai_admin.PriceRow])
async def ai_set_prices(
    data: ai_admin.PricesIn,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await ai_admin.set_prices(session, user, data)
    return await ai_admin.prices(session)


@admin.get("/ai/calibrations", response_model=list[ai_admin.Calibration])
async def ai_calibrations():
    return ai_admin.calibrations()


@admin.get("/ai/quotas", response_model=quota.QuotasOut)
async def ai_quotas(session: AsyncSession = Depends(get_session)):
    """Uso do plano gratuito por modelo (contado pelo app) contra os limites cadastrados."""
    return await quota.report(session)


@admin.put("/ai/quotas", response_model=quota.QuotasOut)
async def ai_set_quotas(
    data: quota.QuotasIn,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    await quota.set_rules(session, user, data)
    return await quota.report(session)


# ---- logs ------------------------------------------------------------------------


@admin.get("/logs", response_model=logs.LogsOut)
async def list_logs(
    level: logs.LevelFilter | None = Query(default=None),
    source: logs.SourceFilter | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """Avisos e erros da API e do worker, já sem dados pessoais."""
    return await logs.list_logs(session, level, source, q, before_id, limit)


@admin.get("/logs/{log_id}", response_model=logs.LogDetail)
async def get_log(log_id: int, session: AsyncSession = Depends(get_session)):
    return await logs.get_log(session, log_id)


@admin.put("/logs/settings", response_model=logs.LogSettings)
async def put_log_settings(
    data: logs.LogSettings,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Prazo de retenção: registros mais antigos são apagados na hora e depois todo dia."""
    return await logs.set_retention(session, user, data)


@admin.delete("/logs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_logs(session: AsyncSession = Depends(get_session)):
    await logs.clear_logs(session)


router.include_router(admin)
