"""Importa todos os models para registrar as tabelas no metadata (Alembic e testes)."""

from app.ai.models import AICredential, AIUsage
from app.core.db import Base
from app.email.models import EmailLog
from app.jobs.models import Job
from app.modules.auth.models import EmailToken, RefreshToken
from app.modules.contests.models import ContestExam, ContestExamQuestion
from app.modules.essays.models import (
    Essay,
    EssayGradingRun,
    EssayImage,
    EssayResult,
    EssayTheme,
)
from app.modules.planner.models import StudyBlock, StudyPlan, StudySession
from app.modules.questions.models import (
    Exam,
    ExamQuestion,
    KnowledgeArea,
    PracticeSession,
    Question,
    QuestionAsset,
    QuestionAttempt,
    QuestionBookmark,
    QuestionOption,
    QuestionTopic,
    Subject,
    Topic,
)
from app.modules.system.models import AppSetting, SystemEvent
from app.modules.users.models import User

metadata = Base.metadata

__all__ = [
    "AICredential",
    "AIUsage",
    "AppSetting",
    "ContestExam",
    "ContestExamQuestion",
    "EmailLog",
    "EmailToken",
    "Essay",
    "EssayGradingRun",
    "EssayImage",
    "EssayResult",
    "EssayTheme",
    "Exam",
    "ExamQuestion",
    "Job",
    "KnowledgeArea",
    "PracticeSession",
    "Question",
    "QuestionAsset",
    "QuestionAttempt",
    "QuestionBookmark",
    "QuestionOption",
    "QuestionTopic",
    "RefreshToken",
    "StudyBlock",
    "StudyPlan",
    "StudySession",
    "Subject",
    "SystemEvent",
    "Topic",
    "User",
    "metadata",
]
