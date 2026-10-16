"""Catálogo (áreas, disciplinas, tópicos) e banco de questões."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import (
    ExamApplication,
    ForeignLanguage,
    PracticeMode,
    QuestionFormat,
    pg_enum,
)

# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


class KnowledgeArea(Base):
    __tablename__ = "knowledge_areas"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    code: Mapped[str] = mapped_column(CHAR(2), unique=True)
    name: Mapped[str] = mapped_column(Text)


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (Index("idx_subjects_area", "area_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    area_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("knowledge_areas.id"))
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text, unique=True)


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("subject_id", "slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Provas e questões
# ---------------------------------------------------------------------------


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("year", "application", "day", "booklet_color"),
        CheckConstraint("day IN (1, 2)", name="exams_day_check"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    application: Mapped[ExamApplication] = mapped_column(
        pg_enum(ExamApplication, "exam_application"), server_default=text("'regular'")
    )
    day: Mapped[int] = mapped_column(SmallInteger)
    booklet_color: Mapped[str] = mapped_column(Text)
    booklet_code: Mapped[int | None] = mapped_column(Integer)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        Index("idx_questions_area_subject", "area_id", "subject_id"),
        Index("idx_questions_year", "year"),
        Index("idx_questions_irt_b", "irt_b"),
        Index("idx_questions_search", "search_vector", postgresql_using="gin"),
        CheckConstraint("skill_code BETWEEN 1 AND 30", name="questions_skill_code_check"),
        CheckConstraint(
            "correct_option IN ('A','B','C','D','E')", name="questions_correct_option_check"
        ),
        # Questão importada ainda em revisão (não publicada) pode estar sem gabarito.
        CheckConstraint(
            "is_annulled OR correct_option IS NOT NULL OR NOT is_published",
            name="answer_or_annulled",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inep_item_code: Mapped[int | None] = mapped_column(Integer, unique=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    area_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("knowledge_areas.id"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    foreign_language: Mapped[ForeignLanguage | None] = mapped_column(
        pg_enum(ForeignLanguage, "foreign_language")
    )
    skill_code: Mapped[int | None] = mapped_column(SmallInteger)
    statement_md: Mapped[str] = mapped_column(Text)
    correct_option: Mapped[str | None] = mapped_column(CHAR(1))
    is_annulled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    irt_a: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    irt_b: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    irt_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 5))
    explanation_md: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default=text("'inep'"))
    format: Mapped[QuestionFormat] = mapped_column(
        pg_enum(QuestionFormat, "question_format"), server_default=text("'multiple_choice'")
    )
    # Só questões publicadas aparecem para os alunos (provas de concurso em revisão ficam ocultas).
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    reviewed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('pt_unaccent'::regconfig, statement_md)", persisted=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (UniqueConstraint("exam_id", "position"),)

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)


class QuestionOption(Base):
    __tablename__ = "question_options"
    __table_args__ = (
        CheckConstraint("letter IN ('A','B','C','D','E')", name="question_options_letter_check"),
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    letter: Mapped[str] = mapped_column(CHAR(1), primary_key=True)
    text_md: Mapped[str] = mapped_column(Text)


class QuestionAsset(Base):
    __tablename__ = "question_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(Text)
    alt_text: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))


class QuestionTopic(Base):
    __tablename__ = "question_topics"
    __table_args__ = (Index("idx_question_topics_topic", "topic_id"),)

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )


# ---------------------------------------------------------------------------
# Prática do aluno
# ---------------------------------------------------------------------------


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (Index("idx_practice_sessions_user", "user_id", text("started_at DESC")),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mode: Mapped[PracticeMode] = mapped_column(
        pg_enum(PracticeMode, "practice_mode"), server_default=text("'livre'")
    )
    filters: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    question_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"
    __table_args__ = (
        Index("idx_attempts_user_time", "user_id", text("answered_at DESC")),
        Index("idx_attempts_user_question", "user_id", "question_id"),
        CheckConstraint(
            "selected_option IN ('A','B','C','D','E')",
            name="question_attempts_selected_option_check",
        ),
        CheckConstraint(
            "time_spent_seconds >= 0", name="question_attempts_time_spent_seconds_check"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    practice_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="SET NULL")
    )
    selected_option: Mapped[str | None] = mapped_column(CHAR(1))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class QuestionBookmark(Base):
    __tablename__ = "question_bookmarks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
