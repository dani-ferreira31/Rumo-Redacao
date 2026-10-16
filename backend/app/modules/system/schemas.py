"""Respostas do painel admin. Só números agregados: nada de nome, e-mail ou conteúdo de aluno."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["ok", "warning", "error"]


class Budget(BaseModel):
    spent_usd: float
    budget_usd: float | None
    pct: float | None
    projected_usd: float
    warning: bool
    exceeded: bool


class Alert(BaseModel):
    level: Level
    message: str
    href: str | None = None


# ---- visão geral -----------------------------------------------------------------


class WeekCount(BaseModel):
    week: date
    count: int


class DayCount(BaseModel):
    day: date
    count: int


class OverviewOut(BaseModel):
    students_total: int
    active_7d: int
    active_30d: int
    signups: list[WeekCount]
    essays_submitted_30d: int
    essays_graded_30d: int
    essays_failed_30d: int
    avg_grading_minutes: float | None
    answers_by_day: list[DayCount]
    answers_30d: int
    budget: Budget
    alerts: list[Alert]


# ---- saúde -----------------------------------------------------------------------


class Check(BaseModel):
    name: str
    level: Level
    detail: str


class HealthOut(BaseModel):
    checks: list[Check]
    disk_free_gb: float | None
    disk_total_gb: float | None
    worker_last_seen: datetime | None


# ---- fila ------------------------------------------------------------------------


class QueueCount(BaseModel):
    queue: str
    pending: int
    running: int
    done: int
    failed: int
    cancelled: int


class JobOut(BaseModel):
    """Sem payload: e-mails e ids de alunos ficam de fora."""

    id: int
    queue: str
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    run_after: datetime
    created_at: datetime
    updated_at: datetime


class JobsOut(BaseModel):
    counts: list[QueueCount]
    jobs: list[JobOut]


# ---- módulos e limites -----------------------------------------------------------


class FeatureOut(BaseModel):
    name: str
    label: str
    enabled: bool


class FeaturesIn(BaseModel):
    features: dict[str, bool]


class Limits(BaseModel):
    essays_per_month: int | None = Field(default=None, ge=1, le=1000)
    ai_budget_usd: float | None = Field(default=None, gt=0, le=100000)


class EventOut(BaseModel):
    id: int
    kind: str
    message: str
    created_at: datetime


# ---- custos ----------------------------------------------------------------------

Period = Literal["month", "last_month", "7d", "30d", "90d"]


class CostDay(BaseModel):
    day: date
    purpose: str
    calls: int
    cost_usd: float


class CostModel(BaseModel):
    provider: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cost_usd: float
    unknown_cost_calls: int


class CostPurpose(BaseModel):
    purpose: str
    calls: int
    cost_usd: float
    units: int
    avg_cost_per_unit_usd: float | None


class CostReport(BaseModel):
    period: Period
    start: datetime
    end: datetime
    total_cost_usd: float
    total_calls: int
    unknown_cost_calls: int
    by_day: list[CostDay]
    by_model: list[CostModel]
    by_purpose: list[CostPurpose]
    budget: Budget
