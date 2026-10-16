"""Schema inicial (gerado a partir de db/schema.sql)

Revision ID: 0001
Revises:
Create Date: 2026-10-14
"""

from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.util import await_

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SQL_FILE = Path(__file__).with_suffix(".sql")

TABLES = [
    "jobs",
    "email_logs",
    "ai_usage",
    "study_sessions",
    "study_blocks",
    "study_plans",
    "question_bookmarks",
    "question_attempts",
    "practice_sessions",
    "question_topics",
    "question_assets",
    "question_options",
    "exam_questions",
    "questions",
    "exams",
    "essay_results",
    "essay_grading_runs",
    "essay_images",
    "essays",
    "essay_themes",
    "topics",
    "subjects",
    "knowledge_areas",
    "refresh_tokens",
    "email_tokens",
    "users",
]
ENUMS = [
    "job_status",
    "ai_purpose",
    "practice_mode",
    "foreign_language",
    "exam_application",
    "essay_zero_reason",
    "essay_input_type",
    "essay_status",
    "email_token_purpose",
    "user_role",
]


def upgrade() -> None:
    # O DDL tem vários comandos e uma função plpgsql; o asyncpg executa o script
    # inteiro pelo protocolo simples (sem prepared statement).
    raw = op.get_bind().connection.driver_connection
    await_(raw.execute(SQL_FILE.read_text(encoding="utf-8")))


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    for enum in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {enum}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS pt_unaccent")
