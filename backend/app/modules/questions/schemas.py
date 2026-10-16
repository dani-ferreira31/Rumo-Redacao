import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import ForeignLanguage, PracticeMode, QuestionFormat

Difficulty = Literal["facil", "media", "dificil"]
StatusFilter = Literal["nao_respondidas", "erradas", "favoritas"]
Track = Literal["enem", "concurso"]
Level = Literal["medio", "superior"]
Letter = Literal["A", "B", "C", "D", "E"]


# ---- catálogo -------------------------------------------------------------------


class TopicOut(BaseModel):
    id: int
    name: str
    slug: str
    parent_id: int | None


class SubjectOut(BaseModel):
    id: int
    name: str
    slug: str
    topics: list[TopicOut]


class AreaOut(BaseModel):
    id: int
    code: str
    name: str
    subjects: list[SubjectOut]


# ---- questões -------------------------------------------------------------------


class QuestionFilters(BaseModel):
    track: Track = Field(default="enem", description="enem ou concurso")
    area: str | None = Field(default=None, description="LC, CH, CN ou MT (só ENEM)")
    subject_id: int | None = None
    topic_id: int | None = None
    year: int | None = None
    difficulty: Difficulty | None = None
    skill: int | None = Field(default=None, ge=1, le=30)
    language: ForeignLanguage | None = None
    status: StatusFilter | None = None
    q: str | None = Field(default=None, max_length=200)
    # só concursos
    board: str | None = Field(default=None, max_length=100, description="Banca")
    organization: str | None = Field(default=None, max_length=100, description="Órgão")
    position: str | None = Field(default=None, max_length=200, description="Cargo")
    level: Level | None = None
    contest_exam_id: int | None = None
    format: QuestionFormat | None = None


class QuestionListQuery(QuestionFilters):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None


class SubjectRef(BaseModel):
    id: int
    name: str


class QuestionListItem(BaseModel):
    id: int
    year: int
    track: Track = "enem"
    format: QuestionFormat = QuestionFormat.multiple_choice
    contest: str | None = Field(default=None, description="Banca · órgão · cargo (concursos)")
    area_code: str
    subject: SubjectRef | None
    skill_code: int | None
    foreign_language: ForeignLanguage | None
    difficulty: Difficulty | None
    preview: str
    bookmarked: bool
    last_attempt_correct: bool | None = Field(
        description="Resultado da última tentativa (null = nunca respondida)."
    )


class QuestionPage(BaseModel):
    items: list[QuestionListItem]
    next_cursor: str | None
    total: int


class OptionOut(BaseModel):
    letter: Letter
    text_md: str


class ExamPosition(BaseModel):
    label: str
    position: int


class QuestionOut(BaseModel):
    """Questão SEM gabarito: ele só aparece na resposta de /answer."""

    id: int
    year: int
    track: Track = "enem"
    format: QuestionFormat = QuestionFormat.multiple_choice
    area_code: str
    area_name: str
    subject: SubjectRef | None
    topics: list[TopicOut]
    skill_code: int | None
    foreign_language: ForeignLanguage | None
    difficulty: Difficulty | None
    statement_md: str
    options: list[OptionOut]
    bookmarked: bool
    positions: list[ExamPosition]


class AnswerIn(BaseModel):
    selected_option: Letter
    time_spent_seconds: int | None = Field(default=None, ge=0, le=6 * 3600)
    practice_session_id: uuid.UUID | None = None


class AnswerOut(BaseModel):
    recorded: bool = True
    is_correct: bool | None = Field(description="null em lista/simulado: o gabarito sai no final.")
    correct_option: Letter | None
    explanation_md: str | None


# ---- sessões de prática ---------------------------------------------------------


class PracticeSessionIn(BaseModel):
    mode: PracticeMode = PracticeMode.livre
    filters: QuestionFilters = QuestionFilters()
    size: int = Field(default=10, ge=1, le=90)
    time_limit_seconds: int | None = Field(default=None, ge=60, le=6 * 3600)


class PracticeSessionOut(BaseModel):
    id: uuid.UUID
    mode: PracticeMode
    filters: QuestionFilters
    question_ids: list[int]
    time_limit_seconds: int | None
    started_at: datetime
    finished_at: datetime | None
    answers: dict[int, Letter] = Field(description="Alternativa escolhida por questão.")


class SessionItemResult(BaseModel):
    question_id: int
    selected_option: Letter | None
    correct_option: Letter | None
    is_correct: bool


class AreaScore(BaseModel):
    code: str
    name: str
    answered: int
    correct: int
    pct: float | None


class SessionResult(BaseModel):
    session: PracticeSessionOut
    total: int
    answered: int
    correct: int
    by_area: list[AreaScore]
    items: list[SessionItemResult]


# ---- estatísticas ---------------------------------------------------------------


class GroupScore(BaseModel):
    id: int | None
    name: str
    answered: int
    correct: int
    pct: float | None


class TimelinePoint(BaseModel):
    week: date
    answered: int
    correct: int


class QuestionStatsOut(BaseModel):
    """Acerto pela ÚLTIMA tentativa de cada questão; a série temporal conta todas."""

    answered: int
    correct: int
    pct: float | None
    by_area: list[AreaScore]
    by_subject: list[GroupScore]
    by_topic: list[GroupScore]
    timeline: list[TimelinePoint]


# ---- admin ----------------------------------------------------------------------


class AdminQuestionOut(QuestionOut):
    correct_option: Letter | None
    explanation_md: str | None
    is_annulled: bool
    reviewed: bool
    inep_item_code: int | None
    irt_a: float | None
    irt_b: float | None
    irt_c: float | None
    source: str
    is_published: bool = True


class AdminQuestionUpdate(BaseModel):
    statement_md: str | None = None
    explanation_md: str | None = None
    subject_id: int | None = None
    topic_ids: list[int] | None = None
    correct_option: Letter | None = None
    is_annulled: bool | None = None
    reviewed: bool | None = None
    format: QuestionFormat | None = None
    options: list[OptionOut] | None = None
