import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(Text)
    to_email: Mapped[str] = mapped_column(CITEXT)
    resend_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    error: Mapped[str | None] = mapped_column(Text)
    # Impede envios duplicados, ex.: reminder:{block_id}:{2026-10-14}
    dedupe_key: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
