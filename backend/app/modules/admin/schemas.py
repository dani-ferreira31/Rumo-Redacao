import uuid

from pydantic import BaseModel, Field

from app.modules.questions.schemas import QuestionListItem


class AdminQuestionPage(BaseModel):
    items: list[QuestionListItem]
    next_cursor: str | None
    total: int


class ThemeIn(BaseModel):
    title: str = Field(min_length=5, max_length=300)
    year: int | None = Field(default=None, ge=1998, le=2100)
    is_official: bool = True
    motivating_texts: str | None = Field(default=None, max_length=20000)


class ThemeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=300)
    year: int | None = Field(default=None, ge=1998, le=2100)
    is_official: bool | None = None
    motivating_texts: str | None = Field(default=None, max_length=20000)


class AdminThemeOut(BaseModel):
    id: uuid.UUID
    title: str
    year: int | None
    is_official: bool
    motivating_texts: str | None
