from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import JobStatus, pg_enum


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_pending", "run_after", postgresql_where=text("status = 'pending'")),
        Index("idx_jobs_running", "locked_at", postgresql_where=text("status = 'running'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    queue: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[JobStatus] = mapped_column(
        pg_enum(JobStatus, "job_status"), server_default=text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("5"))
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
