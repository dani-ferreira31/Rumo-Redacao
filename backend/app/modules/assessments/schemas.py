import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.questions.schemas import Letter, QuestionOut

MAX_QUESTIONS = 120


# ---- professor ----------------------------------------------------------------------


def _clean_title(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("Dê um título à prova.")
    return v


def _check_unique(v: list[int] | None) -> list[int] | None:
    if v is not None and len(set(v)) != len(v):
        raise ValueError("A mesma questão aparece mais de uma vez.")
    return v


class AssessmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str | None = Field(default=None, max_length=5000)
    question_ids: list[int] = Field(min_length=1, max_length=MAX_QUESTIONS)

    _title = field_validator("title")(_clean_title)
    _questions = field_validator("question_ids")(_check_unique)


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    instructions: str | None = Field(default=None, max_length=5000)
    question_ids: list[int] | None = Field(default=None, min_length=1, max_length=MAX_QUESTIONS)
    is_open: bool | None = None

    _title = field_validator("title")(_clean_title)
    _questions = field_validator("question_ids")(_check_unique)


class AssessmentSummary(BaseModel):
    id: uuid.UUID
    title: str
    share_code: str
    url: str
    is_open: bool
    question_count: int
    attempts: int
    finished: int
    created_at: datetime
    updated_at: datetime


class TeacherQuestion(QuestionOut):
    """Questão com gabarito: só o dono da prova (ou o admin) recebe."""

    position: int
    correct_option: Letter | None
    explanation_md: str | None


class AssessmentDetail(AssessmentSummary):
    instructions: str | None
    questions: list[TeacherQuestion]


class AttemptRow(BaseModel):
    """Um aluno que abriu a prova. Nome e e-mail: o aluno é avisado antes de começar."""

    id: uuid.UUID
    student_name: str
    student_email: str
    started_at: datetime
    finished_at: datetime | None
    answered: int
    correct: int | None
    total: int
    pct: float | None
    answers: dict[int, Letter]


class QuestionResult(BaseModel):
    question_id: int
    position: int
    correct_option: Letter | None
    answered: int
    correct: int
    pct: float | None
    distribution: dict[str, int]


class AssessmentResults(BaseModel):
    assessment_id: uuid.UUID
    total_questions: int
    attempts: list[AttemptRow]
    finished: int
    avg_pct: float | None
    questions: list[QuestionResult]


# ---- aluno --------------------------------------------------------------------------


class AttemptInfo(BaseModel):
    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    correct: int | None
    total: int | None


class AssessmentPublic(BaseModel):
    """O que o aluno vê antes de começar (sem questões nem gabarito)."""

    title: str
    instructions: str | None
    teacher_name: str
    question_count: int
    is_open: bool
    attempt: AttemptInfo | None


class AttemptItemResult(BaseModel):
    question_id: int
    selected_option: Letter | None
    correct_option: Letter | None
    is_correct: bool
    explanation_md: str | None


class AttemptOut(BaseModel):
    """Questões SEM gabarito enquanto a prova não for entregue; `result` só depois."""

    attempt: AttemptInfo
    title: str
    instructions: str | None
    is_open: bool
    questions: list[QuestionOut]
    answers: dict[int, Letter]
    result: list[AttemptItemResult] | None = None


class AttemptAnswerIn(BaseModel):
    selected_option: Letter | None = Field(description="null apaga a resposta")
