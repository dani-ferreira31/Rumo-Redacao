import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.modules.planner.schemas import BlockOut


class LastEssay(BaseModel):
    id: uuid.UUID
    theme_title: str
    status: str
    total: int | None
    created_at: datetime


class WeekAccuracy(BaseModel):
    answered: int
    correct: int
    pct: float | None


class DashboardOut(BaseModel):
    today: date
    weekday: int
    today_blocks: list[BlockOut]
    next_block_id: uuid.UUID | None
    last_essay: LastEssay | None
    essays_graded: int
    week_accuracy: WeekAccuracy
    streak_days: int
    studied_today: bool
