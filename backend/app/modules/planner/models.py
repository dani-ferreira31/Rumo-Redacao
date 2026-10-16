import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StudyPlan(Base):
    __tablename__ = "study_plans"
    __table_args__ = (
        # no máximo 1 cronograma ativo por usuário
        Index("uq_study_plans_active", "user_id", unique=True, postgresql_where=text("is_active")),
        CheckConstraint("grid_end > grid_start", name="study_plans_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    grid_start: Mapped[time] = mapped_column(Time, server_default=text("'06:00:00'::time"))
    grid_end: Mapped[time] = mapped_column(Time, server_default=text("'23:30:00'::time"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class StudyBlock(Base):
    """weekday segue a ISO 8601: 1 = segunda ... 7 = domingo."""

    __tablename__ = "study_blocks"
    __table_args__ = (
        Index("idx_study_blocks_plan_day", "plan_id", "weekday", "start_time"),
        Index(
            "idx_study_blocks_reminder",
            "weekday",
            "start_time",
            postgresql_where=text("reminder_minutes_before IS NOT NULL"),
        ),
        CheckConstraint("weekday BETWEEN 1 AND 7", name="study_blocks_weekday_check"),
        CheckConstraint(
            "reminder_minutes_before BETWEEN 0 AND 1440",
            name="study_blocks_reminder_minutes_before_check",
        ),
        CheckConstraint("end_time > start_time", name="study_blocks_check"),
        CheckConstraint(
            "area_id IS NOT NULL OR subject_id IS NOT NULL OR title IS NOT NULL",
            name="study_blocks_check1",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_plans.id", ondelete="CASCADE"))
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    area_id: Mapped[int | None] = mapped_column(SmallInteger, ForeignKey("knowledge_areas.id"))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    title: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    reminder_minutes_before: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class StudySession(Base):
    """Registro do que foi efetivamente estudado (fase posterior)."""

    __tablename__ = "study_sessions"
    __table_args__ = (
        Index("idx_study_sessions_user", "user_id", text("started_at DESC")),
        CheckConstraint("duration_minutes > 0", name="study_sessions_duration_minutes_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("study_blocks.id", ondelete="SET NULL")
    )
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
