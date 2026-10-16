import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import AIPurpose, pg_enum


class AIUsage(Base):
    """Uma linha por chamada a um provedor de IA (custo e depuração)."""

    __tablename__ = "ai_usage"
    __table_args__ = (Index("idx_ai_usage_user_time", "user_id", text("created_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    essay_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("essays.id", ondelete="SET NULL"))
    contest_exam_id: Mapped[int | None] = mapped_column(
        ForeignKey("contest_exams.id", ondelete="SET NULL")
    )
    purpose: Mapped[AIPurpose] = mapped_column(pg_enum(AIPurpose, "ai_purpose"))
    provider: Mapped[str] = mapped_column(Text, server_default=text("'anthropic'"))
    model: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cache_write_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


PROVIDERS = ("anthropic", "openai", "google")


class AICredential(Base):
    """Chave de API de um provedor, criptografada (Fernet). Nunca sai pela API."""

    __tablename__ = "ai_credentials"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('anthropic','openai','google')", name="ai_credentials_provider_check"
        ),
    )

    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary)
    key_hint: Mapped[str] = mapped_column(Text)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_test_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
