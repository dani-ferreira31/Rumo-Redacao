import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import EssayInputType, EssayStatus, EssayZeroReason, pg_enum

VALID_SCORES = "(0, 40, 80, 120, 160, 200)"


class EssayTheme(Base):
    __tablename__ = "essay_themes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(SmallInteger)
    is_official: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    motivating_texts: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Essay(Base):
    __tablename__ = "essays"
    __table_args__ = (
        Index("idx_essays_user", "user_id", text("created_at DESC")),
        Index(
            "idx_essays_status",
            "status",
            postgresql_where=text("status IN ('transcribing', 'grading')"),
        ),
        CheckConstraint("theme_id IS NOT NULL OR custom_theme IS NOT NULL", name="essay_has_theme"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    theme_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("essay_themes.id", ondelete="SET NULL")
    )
    custom_theme: Mapped[str | None] = mapped_column(Text)
    input_type: Mapped[EssayInputType] = mapped_column(pg_enum(EssayInputType, "essay_input_type"))
    status: Mapped[EssayStatus] = mapped_column(
        pg_enum(EssayStatus, "essay_status"), server_default=text("'uploaded'")
    )
    transcription_raw: Mapped[dict | None] = mapped_column(JSONB)
    transcription_text: Mapped[str | None] = mapped_column(Text)
    line_count: Mapped[int | None] = mapped_column(SmallInteger)
    error_message: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class EssayImage(Base):
    __tablename__ = "essay_images"
    __table_args__ = (
        UniqueConstraint("essay_id", "page"),
        CheckConstraint("page BETWEEN 1 AND 2", name="essay_images_page_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    original_storage_key: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class EssayGradingRun(Base):
    """Uma execução independente de correção (simula um corretor)."""

    __tablename__ = "essay_grading_runs"
    __table_args__ = (
        UniqueConstraint("essay_id", "run_number"),
        CheckConstraint("run_number BETWEEN 1 AND 5", name="essay_grading_runs_run_number_check"),
        *(
            CheckConstraint(f"c{i} IN {VALID_SCORES}", name=f"essay_grading_runs_c{i}_check")
            for i in range(1, 6)
        ),
        CheckConstraint("NOT annulled OR (c1 + c2 + c3 + c4 + c5) = 0", name="annulled_means_zero"),
        CheckConstraint("annulled = (zero_reason IS NOT NULL)", name="annulled_has_reason"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    essay_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("essays.id", ondelete="CASCADE"))
    run_number: Mapped[int] = mapped_column(SmallInteger)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    c1: Mapped[int] = mapped_column(SmallInteger)
    c2: Mapped[int] = mapped_column(SmallInteger)
    c3: Mapped[int] = mapped_column(SmallInteger)
    c4: Mapped[int] = mapped_column(SmallInteger)
    c5: Mapped[int] = mapped_column(SmallInteger)
    total: Mapped[int] = mapped_column(
        SmallInteger, Computed("c1 + c2 + c3 + c4 + c5", persisted=True)
    )
    annulled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    zero_reason: Mapped[EssayZeroReason | None] = mapped_column(
        pg_enum(EssayZeroReason, "essay_zero_reason")
    )
    feedback: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class EssayResult(Base):
    """Resultado consolidado mostrado ao aluno (médias: qualquer valor entre 0 e 200)."""

    __tablename__ = "essay_results"
    __table_args__ = tuple(
        CheckConstraint(f"c{i} BETWEEN 0 AND 200", name=f"essay_results_c{i}_check")
        for i in range(1, 6)
    )

    essay_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("essays.id", ondelete="CASCADE"), primary_key=True
    )
    c1: Mapped[int] = mapped_column(SmallInteger)
    c2: Mapped[int] = mapped_column(SmallInteger)
    c3: Mapped[int] = mapped_column(SmallInteger)
    c4: Mapped[int] = mapped_column(SmallInteger)
    c5: Mapped[int] = mapped_column(SmallInteger)
    total: Mapped[int] = mapped_column(
        SmallInteger, Computed("c1 + c2 + c3 + c4 + c5", persisted=True)
    )
    annulled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    zero_reason: Mapped[EssayZeroReason | None] = mapped_column(
        pg_enum(EssayZeroReason, "essay_zero_reason")
    )
    runs_used: Mapped[int] = mapped_column(SmallInteger)
    needed_third_run: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    feedback: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
