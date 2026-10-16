"""Enums do Postgres (criados pela migration inicial) espelhados em Python."""

from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class UserRole(StrEnum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class EmailTokenPurpose(StrEnum):
    verify_email = "verify_email"
    reset_password = "reset_password"


class EssayStatus(StrEnum):
    uploaded = "uploaded"
    transcribing = "transcribing"
    awaiting_review = "awaiting_review"
    grading = "grading"
    graded = "graded"
    failed = "failed"


class EssayInputType(StrEnum):
    photo = "photo"
    text = "text"


class EssayZeroReason(StrEnum):
    folha_em_branco = "folha_em_branco"
    texto_insuficiente = "texto_insuficiente"
    fuga_total_ao_tema = "fuga_total_ao_tema"
    nao_dissertativo_argumentativo = "nao_dissertativo_argumentativo"
    parte_desconectada = "parte_desconectada"
    copia_textos_motivadores = "copia_textos_motivadores"
    lingua_estrangeira = "lingua_estrangeira"
    identificacao = "identificacao"
    improperios_ou_anulacao = "improperios_ou_anulacao"
    ilegivel = "ilegivel"


class ExamApplication(StrEnum):
    regular = "regular"
    reaplicacao = "reaplicacao"
    digital = "digital"
    ppl = "ppl"


class ForeignLanguage(StrEnum):
    ingles = "ingles"
    espanhol = "espanhol"


class PracticeMode(StrEnum):
    livre = "livre"
    lista = "lista"
    simulado = "simulado"


class AIPurpose(StrEnum):
    transcription = "transcription"
    grading = "grading"
    planner = "planner"
    other = "other"
    contest_extraction = "contest_extraction"


class QuestionFormat(StrEnum):
    multiple_choice = "multiple_choice"
    true_false = "true_false"  # Certo/Errado: correct_option "C" ou "E"


class ContestExamStatus(StrEnum):
    processing = "processing"
    review = "review"
    published = "published"
    failed = "failed"


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


def pg_enum(enum_cls: type[StrEnum], name: str) -> ENUM:
    return ENUM(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )
