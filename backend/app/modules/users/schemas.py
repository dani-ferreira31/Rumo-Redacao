import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.core.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str
    role: UserRole
    email_verified_at: datetime | None
    birth_date: date | None
    timezone: str
    target_exam_year: int | None
    email_reminders_enabled: bool
    created_at: datetime

    @computed_field
    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    timezone: str | None = None
    target_exam_year: int | None = Field(default=None, ge=2020, le=2100)
    email_reminders_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Informe seu nome.")
        return v

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Fuso horário inválido.") from exc
        return v


class UnsubscribeOut(BaseModel):
    email_reminders_enabled: bool
