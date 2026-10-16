import re
import uuid
from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _check_step(t: time | None) -> time | None:
    if t is None:
        return t
    if t.second or t.microsecond or t.minute % 5:
        raise ValueError("Use horários em múltiplos de 5 minutos.")
    return t


class PlanIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    grid_start: time = time(6, 0)
    grid_end: time = time(23, 30)

    _step = field_validator("grid_start", "grid_end")(_check_step)

    @model_validator(mode="after")
    def _range(self):
        if self.grid_end <= self.grid_start:
            raise ValueError("O fim da grade deve ser depois do início.")
        return self


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    grid_start: time | None = None
    grid_end: time | None = None

    _step = field_validator("grid_start", "grid_end")(_check_step)


class BlockIn(BaseModel):
    weekday: int = Field(ge=1, le=7, description="ISO 8601: 1 = segunda ... 7 = domingo")
    start_time: time
    end_time: time
    area_id: int | None = None
    subject_id: int | None = None
    title: str | None = Field(default=None, max_length=120)
    color: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    reminder_minutes_before: int | None = Field(default=None, ge=0, le=1440)

    _step = field_validator("start_time", "end_time")(_check_step)

    @field_validator("title", "notes")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v is not None else None

    @field_validator("color")
    @classmethod
    def _color(cls, v: str | None) -> str | None:
        if v is not None and not HEX_RE.match(v):
            raise ValueError("Cor deve estar no formato #RRGGBB.")
        return v

    @model_validator(mode="after")
    def _rules(self):
        if self.end_time <= self.start_time:
            raise ValueError(
                "O bloco deve terminar depois de começar (blocos não cruzam a meia-noite)."
            )
        if self.area_id is None and self.subject_id is None and not self.title:
            raise ValueError("Informe a área, a disciplina ou um título.")
        return self


class BlockUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    area_id: int | None = None
    subject_id: int | None = None
    title: str | None = Field(default=None, max_length=120)
    color: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    reminder_minutes_before: int | None = Field(default=None, ge=0, le=1440)


class BlockOut(BaseModel):
    id: uuid.UUID
    weekday: int
    start_time: time
    end_time: time
    area_id: int | None
    area_code: str | None
    subject_id: int | None
    subject_name: str | None
    title: str | None
    color: str
    notes: str | None
    reminder_minutes_before: int | None


class PlanOut(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    grid_start: time
    grid_end: time
    created_at: datetime
    blocks: list[BlockOut]


class PlanListItem(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    block_count: int
    weekly_hours: float


class HoursBy(BaseModel):
    key: str
    label: str
    hours: float


class PlanSummary(BaseModel):
    total_hours: float
    by_area: list[HoursBy]
    by_day: list[HoursBy]
