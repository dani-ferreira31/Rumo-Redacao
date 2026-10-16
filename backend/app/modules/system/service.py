"""Painel admin: saúde, fila, visão geral e custos. Só agregados (ver schemas.py)."""

import asyncio
import re
import shutil
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, cast, distinct, func, select, union_all, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.models import AICredential, AIUsage
from app.core.config import get_settings
from app.core.enums import EssayStatus, JobStatus, UserRole
from app.core.errors import AppError, NotFoundError
from app.jobs.models import Job
from app.modules.auth.models import RefreshToken
from app.modules.essays.models import Essay
from app.modules.questions.models import QuestionAttempt
from app.modules.system import budget as budget_mod
from app.modules.system import quota as quota_mod
from app.modules.system.models import AppSetting
from app.modules.system.schemas import (
    Alert,
    Budget,
    Check,
    CostDay,
    CostModel,
    CostPurpose,
    CostReport,
    DayCount,
    HealthOut,
    JobOut,
    JobsOut,
    OverviewOut,
    Period,
    QueueCount,
    WeekCount,
)
from app.modules.system.settings import log_event, set_setting
from app.modules.users.models import User
from app.storage import LocalStorage

TZ_NAME = "America/Sao_Paulo"
WORKER_STALE = timedelta(minutes=2)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def mask_personal(text: str | None) -> str | None:
    """Erros de job podem citar o destinatário de um e-mail: mascara antes de mostrar."""
    return _EMAIL.sub("[e-mail]", text) if text else text


def _budget(status: budget_mod.BudgetStatus) -> Budget:
    return Budget(**asdict(status))


# ---- batimento do worker ---------------------------------------------------------


async def record_heartbeat(session: AsyncSession) -> None:
    await set_setting(session, "worker_heartbeat", {"at": datetime.now(UTC).isoformat()})
    await session.commit()


async def worker_last_seen(session: AsyncSession) -> datetime | None:
    # leitura direta, sem o cache das configurações
    value = await session.scalar(
        select(AppSetting.value).where(AppSetting.key == "worker_heartbeat")
    )
    return datetime.fromisoformat(value["at"]) if value and value.get("at") else None


# ---- saúde -----------------------------------------------------------------------


async def health(session: AsyncSession, storage: LocalStorage) -> HealthOut:
    settings = get_settings()
    checks: list[Check] = []
    try:
        await session.execute(select(1))
        checks.append(Check(name="Banco de dados", level="ok", detail="Respondendo"))
    except Exception as exc:  # pragma: no cover
        checks.append(Check(name="Banco de dados", level="error", detail=type(exc).__name__))

    ok = await storage.healthcheck()
    free = total = None
    try:
        usage = await asyncio.to_thread(shutil.disk_usage, storage.root)
        free, total = usage.free / 1e9, usage.total / 1e9
    except OSError:
        pass
    level = "ok" if ok else "error"
    detail = "Gravando normalmente" if ok else "Falha ao gravar"
    if ok and free is not None and total and free / total < 0.1:
        level, detail = "warning", f"Pouco espaço livre: {free:.1f} GB"
    checks.append(Check(name="Armazenamento de arquivos", level=level, detail=detail))

    seen = await worker_last_seen(session)
    if seen is None:
        checks.append(Check(name="Worker (fila)", level="error", detail="Nunca deu sinal de vida"))
    elif datetime.now(UTC) - seen > WORKER_STALE:
        checks.append(
            Check(name="Worker (fila)", level="error", detail="Parado: sem sinal há mais de 2 min")
        )
    else:
        checks.append(Check(name="Worker (fila)", level="ok", detail="Ativo"))

    if settings.email_driver == "console":
        checks.append(
            Check(name="E-mail", level="warning", detail="Modo console: e-mails só no log")
        )
    elif not settings.resend_api_key:
        checks.append(Check(name="E-mail", level="error", detail="RESEND_API_KEY ausente"))
    else:
        domain = settings.email_from.rsplit("@", 1)[-1].rstrip(">")
        checks.append(Check(name="E-mail", level="ok", detail=f"Resend, domínio {domain}"))

    creds = {c.provider: c for c in await session.scalars(select(AICredential))}
    for provider, label in (("anthropic", "Anthropic"), ("openai", "OpenAI"), ("google", "Google")):
        cred = creds.get(provider)
        if cred is None:
            continue
        if cred.last_test_ok is False:
            checks.append(Check(name=f"IA: {label}", level="error", detail="Último teste falhou"))
        elif cred.last_test_ok:
            checks.append(Check(name=f"IA: {label}", level="ok", detail="Chave testada"))
        else:
            checks.append(Check(name=f"IA: {label}", level="warning", detail="Chave não testada"))

    return HealthOut(
        checks=checks,
        disk_free_gb=round(free, 1) if free is not None else None,
        disk_total_gb=round(total, 1) if total is not None else None,
        worker_last_seen=seen,
    )


# ---- fila ------------------------------------------------------------------------


async def jobs(session: AsyncSession, status: JobStatus | None, limit: int) -> JobsOut:
    rows = await session.execute(
        select(Job.queue, Job.status, func.count()).group_by(Job.queue, Job.status)
    )
    counts: dict[str, dict[str, int]] = {}
    for queue, st, n in rows:
        counts.setdefault(queue, {s.value: 0 for s in JobStatus})[str(st)] = n
    stmt = select(Job).order_by(Job.updated_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    else:
        stmt = stmt.where(Job.status.in_([JobStatus.failed, JobStatus.running, JobStatus.pending]))
    items = [
        JobOut(
            id=j.id,
            queue=j.queue,
            status=str(j.status),
            attempts=j.attempts,
            max_attempts=j.max_attempts,
            last_error=mask_personal(j.last_error[:500] if j.last_error else None),
            run_after=j.run_after,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in await session.scalars(stmt)
    ]
    return JobsOut(counts=[QueueCount(queue=q, **c) for q, c in sorted(counts.items())], jobs=items)


async def retry_job(session: AsyncSession, job_id: int) -> None:
    job = await session.get(Job, job_id, with_for_update=True)
    if job is None:
        raise NotFoundError("Job não encontrado.")
    if job.status not in (JobStatus.failed, JobStatus.cancelled):
        raise AppError(
            "job_not_retryable", "Só dá para reprocessar jobs com falha ou cancelados.", 409
        )
    job.status = JobStatus.pending
    job.attempts = 0
    job.run_after = datetime.now(UTC)
    job.locked_at = None
    log_event(session, "job", f"Job {job.id} ({job.queue}) reprocessado pelo admin")
    await session.commit()


async def cancel_job(session: AsyncSession, job_id: int) -> None:
    result = await session.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_([JobStatus.pending, JobStatus.failed]))
        .values(status=JobStatus.cancelled, locked_at=None)
        .returning(Job.queue)
    )
    queue = result.scalar_one_or_none()
    if queue is None:
        raise AppError(
            "job_not_cancellable", "Só dá para cancelar jobs pendentes ou com falha.", 409
        )
    log_event(session, "job", f"Job {job_id} ({queue}) cancelado pelo admin")
    await session.commit()


# ---- visão geral -----------------------------------------------------------------


def _local_day(column):
    return cast(func.timezone(TZ_NAME, column), Date)


async def _active_users(session: AsyncSession, since: datetime) -> int:
    """Alunos (não admins) que entraram, responderam questões ou enviaram redação."""
    activity = union_all(
        select(QuestionAttempt.user_id.label("u")).where(QuestionAttempt.answered_at >= since),
        select(Essay.user_id.label("u")).where(Essay.created_at >= since),
        select(RefreshToken.user_id.label("u")).where(RefreshToken.created_at >= since),
    ).subquery()
    return (
        await session.scalar(
            select(func.count(distinct(activity.c.u)))
            .join(User, User.id == activity.c.u)
            .where(User.role == UserRole.student)
        )
        or 0
    )


async def overview(session: AsyncSession) -> OverviewOut:
    now = datetime.now(UTC)
    d30 = now - timedelta(days=30)
    students = await session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.student)
    )

    week = cast(func.date_trunc("week", func.timezone(TZ_NAME, User.created_at)), Date)
    signups = [
        WeekCount(week=w, count=n)
        for w, n in await session.execute(
            select(week, func.count())
            .where(User.role == UserRole.student, User.created_at >= now - timedelta(weeks=8))
            .group_by(week)
            .order_by(week)
        )
    ]

    submitted, graded, failed, avg_seconds = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(Essay.status == EssayStatus.graded),
                func.count().filter(Essay.status == EssayStatus.failed),
                func.avg(func.extract("epoch", Essay.graded_at - Essay.confirmed_at)).filter(
                    Essay.graded_at.is_not(None)
                ),
            ).where(Essay.created_at >= d30)
        )
    ).one()

    day = _local_day(QuestionAttempt.answered_at)
    answers = [
        DayCount(day=d, count=n)
        for d, n in await session.execute(
            select(day, func.count())
            .where(QuestionAttempt.answered_at >= d30)
            .group_by(day)
            .order_by(day)
        )
    ]

    status = await budget_mod.budget_status(session, now)
    health_alerts: list[Alert] = []
    seen = await worker_last_seen(session)
    if seen is None or now - seen > WORKER_STALE:
        health_alerts.append(
            Alert(
                level="error",
                message="O worker está parado: redações e e-mails não andam.",
                href="/admin/sistema",
            )
        )
    failed_jobs = await session.scalar(
        select(func.count()).select_from(Job).where(Job.status == JobStatus.failed)
    )
    if failed_jobs:
        health_alerts.append(
            Alert(
                level="warning",
                message=f"{failed_jobs} job(s) com falha na fila.",
                href="/admin/sistema",
            )
        )
    if status.exceeded:
        health_alerts.append(
            Alert(
                level="error",
                message="Orçamento de IA do mês atingido: envios pausados.",
                href="/admin/custos",
            )
        )
    elif status.warning:
        health_alerts.append(
            Alert(
                level="warning",
                message=f"Gasto com IA em {status.pct:.0f}% do orçamento.",
                href="/admin/custos",
            )
        )
    # só a cota do dia vira alerta: o limite por minuto oscila e se resolve sozinho
    for q in (await quota_mod.report(session, now)).quotas:
        pct = q.rpd.pct
        if pct is not None and pct >= quota_mod.WARN_PCT:
            health_alerts.append(
                Alert(
                    level="error" if pct >= 100 else "warning",
                    message=f"Cota gratuita do dia ({q.rule.model_match}) em {pct:.0f}%.",
                    href="/admin/ia",
                )
            )
    bad_keys = await session.scalars(
        select(AICredential.provider).where(AICredential.last_test_ok.is_(False))
    )
    for provider in bad_keys:
        health_alerts.append(
            Alert(
                level="error",
                message=f"A chave da {provider} falhou no último teste.",
                href="/admin/ia",
            )
        )

    return OverviewOut(
        students_total=students or 0,
        active_7d=await _active_users(session, now - timedelta(days=7)),
        active_30d=await _active_users(session, d30),
        signups=signups,
        essays_submitted_30d=submitted or 0,
        essays_graded_30d=graded or 0,
        essays_failed_30d=failed or 0,
        avg_grading_minutes=round(float(avg_seconds) / 60, 1) if avg_seconds else None,
        answers_by_day=answers,
        answers_30d=sum(a.count for a in answers),
        budget=_budget(status),
        alerts=health_alerts,
    )


# ---- custos ----------------------------------------------------------------------


def period_bounds(period: Period, now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(UTC)
    if period == "month":
        return budget_mod.month_start(now), now
    if period == "last_month":
        start = budget_mod.month_start(now, months_back=1)
        return start, budget_mod.next_month_start(start)
    days = {"7d": 7, "30d": 30, "90d": 90}[period]
    return now - timedelta(days=days), now


async def cost_report(session: AsyncSession, period: Period) -> CostReport:
    start, end = period_bounds(period)
    in_period = (AIUsage.created_at >= start, AIUsage.created_at < end)
    cost = func.coalesce(func.sum(AIUsage.cost_usd), 0)
    unknown = func.count().filter(AIUsage.cost_usd.is_(None))

    day = _local_day(AIUsage.created_at)
    by_day = [
        CostDay(day=d, purpose=str(p), calls=n, cost_usd=float(c))
        for d, p, n, c in await session.execute(
            select(day, AIUsage.purpose, func.count(), cost)
            .where(*in_period)
            .group_by(day, AIUsage.purpose)
            .order_by(day)
        )
    ]
    by_model = [
        CostModel(
            provider=prov,
            model=model,
            calls=n,
            input_tokens=i or 0,
            output_tokens=o or 0,
            cache_read_tokens=r or 0,
            cost_usd=float(c),
            unknown_cost_calls=u,
        )
        for prov, model, n, i, o, r, c, u in await session.execute(
            select(
                AIUsage.provider,
                AIUsage.model,
                func.count(),
                func.sum(AIUsage.input_tokens),
                func.sum(AIUsage.output_tokens),
                func.sum(AIUsage.cache_read_tokens),
                cost,
                unknown,
            )
            .where(*in_period)
            .group_by(AIUsage.provider, AIUsage.model)
            .order_by(cost.desc())
        )
    ]

    # custo médio por unidade (redação ou prova): só chamadas ligadas a uma delas,
    # então a calibração fica de fora
    linked = AIUsage.essay_id.is_not(None) | AIUsage.contest_exam_id.is_not(None)
    unit_cost = func.coalesce(func.sum(AIUsage.cost_usd).filter(linked), 0)
    units_col = func.count(distinct(AIUsage.essay_id)) + func.count(
        distinct(AIUsage.contest_exam_id)
    )
    by_purpose = []
    for purpose, n, c, units, uc in await session.execute(
        select(AIUsage.purpose, func.count(), cost, units_col, unit_cost)
        .where(*in_period)
        .group_by(AIUsage.purpose)
        .order_by(cost.desc())
    ):
        by_purpose.append(
            CostPurpose(
                purpose=str(purpose),
                calls=n,
                cost_usd=float(c),
                units=units,
                avg_cost_per_unit_usd=round(float(uc) / units, 4) if units else None,
            )
        )

    totals = (await session.execute(select(func.count(), cost, unknown).where(*in_period))).one()
    return CostReport(
        period=period,
        start=start,
        end=end,
        total_cost_usd=round(float(totals[1]), 6),
        total_calls=totals[0],
        unknown_cost_calls=totals[2],
        by_day=by_day,
        by_model=by_model,
        by_purpose=by_purpose,
        budget=_budget(await budget_mod.budget_status(session)),
    )
