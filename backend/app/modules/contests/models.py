import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import ContestExamStatus, pg_enum


class ContestExam(Base):
    """Prova de concurso importada de PDF (prova + gabarito)."""

    __tablename__ = "contest_exams"
    __table_args__ = (Index("idx_contest_exams_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board: Mapped[str] = mapped_column(Text)  # banca: Cebraspe, FGV, FCC...
    organization: Mapped[str] = mapped_column(Text)  # órgão: PF, INSS, TRF1...
    position: Mapped[str] = mapped_column(Text)  # cargo
    level: Mapped[str | None] = mapped_column(Text)  # medio | superior
    year: Mapped[int] = mapped_column(SmallInteger)
    booklet: Mapped[str | None] = mapped_column(Text)  # tipo/cor do caderno, para o gabarito
    status: Mapped[ContestExamStatus] = mapped_column(
        pg_enum(ContestExamStatus, "contest_exam_status"), server_default=text("'processing'")
    )
    exam_key: Mapped[str] = mapped_column(Text)
    answer_key_key: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(SmallInteger)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContestExamQuestion(Base):
    __tablename__ = "contest_exam_questions"

    contest_exam_id: Mapped[int] = mapped_column(
        ForeignKey("contest_exams.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger)
    page: Mapped[int | None] = mapped_column(SmallInteger)
    # Avisos da importação para a revisão (ex.: "sem gabarito", "tem figura na página 3").
    warnings: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
