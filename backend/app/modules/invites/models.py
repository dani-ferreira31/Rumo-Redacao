import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import UserRole, pg_enum


class Invite(Base):
    """Link de convite: o cadastro só acontece por um convite válido."""

    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint("max_uses IS NULL OR max_uses > 0", name="invites_max_uses_check"),
        CheckConstraint("role <> 'admin'", name="invites_role_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"))
    note: Mapped[str | None] = mapped_column(Text)
    max_uses: Mapped[int | None] = mapped_column(Integer)  # None = sem limite
    uses: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
