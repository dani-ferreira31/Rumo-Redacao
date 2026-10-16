from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import ContestExamStatus, QuestionFormat


class ContestMetaIn(BaseModel):
    board: str = Field(min_length=1, max_length=100)
    organization: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=200)
    level: Literal["medio", "superior"] | None = None
    year: int = Field(ge=1990, le=2100)
    booklet: str | None = Field(default=None, max_length=50)


class EstimateOut(BaseModel):
    pages: int
    chunks: int
    provider: str
    model: str
    estimated_cost_usd: float | None
    budget_left_usd: float | None
    budget_exceeded: bool


class ContestExamOut(BaseModel):
    id: int
    board: str
    organization: str
    position: str
    level: str | None
    year: int
    booklet: str | None
    status: ContestExamStatus
    page_count: int | None
    error: str | None
    has_answer_key: bool
    questions: int
    warnings: int
    created_at: datetime
    published_at: datetime | None


class ContestQuestionOut(BaseModel):
    id: int
    position: int
    page: int | None
    format: QuestionFormat
    preview: str
    subject_id: int | None
    subject_name: str | None
    correct_option: str | None
    is_annulled: bool
    options: int
    assets: int
    warnings: list[str]


class ContestExamDetail(ContestExamOut):
    questions_list: list[ContestQuestionOut]
    page_urls: list[str]
    notes: list[str] = []


class FigureIn(BaseModel):
    page: int = Field(ge=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    alt: str = Field(default="Figura", max_length=200)


class SubjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class ContestFiltersOut(BaseModel):
    """Valores existentes nas provas publicadas (para os filtros do aluno)."""

    boards: list[str]
    organizations: list[str]
    positions: list[str]
    years: list[int]
    levels: list[str]
    exams: list[dict]
