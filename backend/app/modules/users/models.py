import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import UserRole, pg_enum


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"), server_default=text("'student'")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    birth_date: Mapped[date | None] = mapped_column(Date)
    guardian_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(Text, server_default=text("'America/Sao_Paulo'"))
    target_exam_year: Mapped[int | None] = mapped_column(SmallInteger)
    email_reminders_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    # Conta bloqueada pelo admin: não entra nem renova a sessão.
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invite_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("invites.id", ondelete="SET NULL", use_alter=True, name="users_invite_id_fkey")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
