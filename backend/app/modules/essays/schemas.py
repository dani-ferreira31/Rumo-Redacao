import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.enums import EssayInputType, EssayStatus, EssayZeroReason


class ThemeOut(BaseModel):
    id: uuid.UUID
    title: str
    year: int | None
    is_official: bool
    has_motivating_texts: bool


class EssayImageOut(BaseModel):
    page: int
    url: str | None = Field(description="Imagem pré-processada (a que a IA leu).")
    original_url: str


class TranscriptionInfo(BaseModel):
    title: str | None
    confidence: str | None
    observations: str | None
    possible_identification: bool
    illegible_count: int


class ExcerptOut(BaseModel):
    line: int | None = None
    text: str
    comment: str


class CompetencyOut(BaseModel):
    number: int
    score: int
    level_summary: str
    justification: str
    strengths: list[str]
    improvements: list[str]
    excerpts: list[ExcerptOut]


class DeviationOut(BaseModel):
    line: int | None = None
    text: str
    type: str
    suggestion: str


class C5ElementOut(BaseModel):
    present: bool
    excerpt: str | None


class ResultOut(BaseModel):
    total: int
    scores: list[int] = Field(description="Notas C1 a C5.")
    annulled: bool
    zero_reason: EssayZeroReason | None
    competencies: list[CompetencyOut]
    c1_deviations: list[DeviationOut]
    c5_elements: dict[str, C5ElementOut] | None
    tangent: bool = False
    human_rights_violation: bool = False
    general_comment: str
    next_steps: list[str]
    warnings: list[str]
    needed_third_run: bool
    simulated: bool = Field(description="Correção feita pela IA falsa (modo de desenvolvimento).")


class EssayOut(BaseModel):
    id: uuid.UUID
    status: EssayStatus
    input_type: EssayInputType
    theme: ThemeOut | None
    custom_theme: str | None
    theme_title: str
    transcription_text: str | None
    transcription: TranscriptionInfo | None
    line_count: int | None
    images: list[EssayImageOut]
    error_message: str | None
    created_at: datetime
    confirmed_at: datetime | None
    graded_at: datetime | None
    result: ResultOut | None


class EssaySummary(BaseModel):
    id: uuid.UUID
    status: EssayStatus
    input_type: EssayInputType
    theme_title: str
    total: int | None
    annulled: bool | None
    created_at: datetime
    graded_at: datetime | None


class EssayPage(BaseModel):
    items: list[EssaySummary]
    next_cursor: str | None


class TranscriptionIn(BaseModel):
    text: str = Field(max_length=20000)


class ConfirmIn(BaseModel):
    text: str | None = Field(default=None, max_length=20000)


class StatsPoint(BaseModel):
    essay_id: uuid.UUID
    date: date
    graded_at: datetime
    theme_title: str
    c1: int
    c2: int
    c3: int
    c4: int
    c5: int
    total: int
    annulled: bool


class StatsOut(BaseModel):
    points: list[StatsPoint]
    averages: dict[str, float] | None
