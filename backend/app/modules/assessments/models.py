import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Assessment(Base):
    """Prova montada por um professor com questões do banco."""

    __tablename__ = "assessments"
    __table_args__ = (Index("idx_assessments_teacher", "teacher_id", text("created_at DESC")),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    # Código do link que o professor manda aos alunos (/provas/<código>).
    share_code: Mapped[str] = mapped_column(Text, unique=True)
    # Fechada, ninguém novo começa nem envia respostas.
    is_open: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)


class AssessmentAttempt(Base):
    """Uma por aluno e prova. O gabarito só aparece depois de `finished_at`."""

    __tablename__ = "assessment_attempts"
    __table_args__ = (UniqueConstraint("assessment_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correct: Mapped[int | None] = mapped_column(SmallInteger)
    total: Mapped[int | None] = mapped_column(SmallInteger)


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    selected_option: Mapped[str] = mapped_column(CHAR(1))
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
