import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import UserRole

InviteRole = Literal[UserRole.student, UserRole.teacher]
InviteStatus = Literal["active", "expired", "used_up", "revoked"]


class InviteIn(BaseModel):
    role: InviteRole
    note: str | None = Field(default=None, max_length=200, description="Para quem é o convite")
    max_uses: int | None = Field(default=None, ge=1, le=10000, description="null = sem limite")
    expires_in_days: int | None = Field(default=None, ge=1, le=365, description="null = não vence")


class InviteOut(BaseModel):
    id: uuid.UUID
    code: str
    url: str
    role: UserRole
    note: str | None
    max_uses: int | None
    uses: int
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    status: InviteStatus


class InvitePublic(BaseModel):
    """O que a tela de cadastro precisa saber do convite (sem dados de quem criou)."""

    role: UserRole
    expires_at: datetime | None
