import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppSetting(Base):
    """Configuração editável pelo painel admin (módulos, limites, IA, preços)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class SystemEvent(Base):
    """Registro das ações do admin e de eventos do sistema. Nunca guarda dados de alunos."""

    __tablename__ = "system_events"
    __table_args__ = (Index("idx_system_events_time", text("created_at DESC")),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AppLog(Base):
    """Aviso ou erro da API/worker (Admin → Logs). Gravado já sem dados pessoais
    (`app/core/applog.scrub`) e apagado após o prazo de retenção do painel."""

    __tablename__ = "app_logs"
    __table_args__ = (
        Index("idx_app_logs_time", text("created_at DESC")),
        Index("idx_app_logs_level_time", "level", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    level: Mapped[str] = mapped_column(Text)  # WARNING | ERROR | CRITICAL
    source: Mapped[str] = mapped_column(Text)  # api | worker
    logger: Mapped[str] = mapped_column(Text)
    event: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
