"""Concursos: área própria, provas importadas de PDF, Certo/Errado e publicação

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SUBJECTS = [
    ("Língua Portuguesa (concursos)", "cp-portugues"),
    ("Raciocínio Lógico", "cp-raciocinio-logico"),
    ("Matemática (concursos)", "cp-matematica"),
    ("Informática", "cp-informatica"),
    ("Direito Constitucional", "cp-direito-constitucional"),
    ("Direito Administrativo", "cp-direito-administrativo"),
    ("Direito Penal", "cp-direito-penal"),
    ("Direito Processual Penal", "cp-direito-processual-penal"),
    ("Direito Civil", "cp-direito-civil"),
    ("Administração Pública", "cp-administracao-publica"),
    ("Administração Geral", "cp-administracao-geral"),
    ("Contabilidade", "cp-contabilidade"),
    ("Legislação Específica", "cp-legislacao"),
    ("Ética no Serviço Público", "cp-etica"),
    ("Atualidades", "cp-atualidades"),
    ("Língua Inglesa (concursos)", "cp-ingles"),
]


def upgrade() -> None:
    op.execute("ALTER TYPE ai_purpose ADD VALUE IF NOT EXISTS 'contest_extraction'")
    op.execute("CREATE TYPE question_format AS ENUM ('multiple_choice', 'true_false')")
    op.execute(
        "CREATE TYPE contest_exam_status AS ENUM ('processing', 'review', 'published', 'failed')"
    )

    op.add_column(
        "questions",
        sa.Column(
            "format",
            postgresql.ENUM(name="question_format", create_type=False),
            server_default=sa.text("'multiple_choice'"),
            nullable=False,
        ),
    )
    op.add_column(
        "questions",
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.drop_constraint("answer_or_annulled", "questions", type_="check")
    op.create_check_constraint(
        "answer_or_annulled",
        "questions",
        "is_annulled OR correct_option IS NOT NULL OR NOT is_published",
    )

    op.execute(
        "INSERT INTO knowledge_areas (id, code, name) VALUES (5, 'CP', 'Concursos públicos')"
    )
    values = ", ".join(f"(5, '{name}', '{slug}')" for name, slug in SUBJECTS)
    op.execute(f"INSERT INTO subjects (area_id, name, slug) VALUES {values}")

    op.create_table(
        "contest_exams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("board", sa.Text(), nullable=False),
        sa.Column("organization", sa.Text(), nullable=False),
        sa.Column("position", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("booklet", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="contest_exam_status", create_type=False),
            server_default=sa.text("'processing'"),
            nullable=False,
        ),
        sa.Column("exam_key", sa.Text(), nullable=False),
        sa.Column("answer_key_key", sa.Text(), nullable=True),
        sa.Column("page_count", sa.SmallInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="contest_exams_created_by_fkey", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="contest_exams_pkey"),
    )
    op.create_index("idx_contest_exams_status", "contest_exams", ["status"])
    op.create_table(
        "contest_exam_questions",
        sa.Column("contest_exam_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("page", sa.SmallInteger(), nullable=True),
        sa.Column(
            "warnings",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contest_exam_id"],
            ["contest_exams.id"],
            name="contest_exam_questions_contest_exam_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name="contest_exam_questions_question_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "contest_exam_id", "question_id", name="contest_exam_questions_pkey"
        ),
    )
    op.add_column("ai_usage", sa.Column("contest_exam_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "ai_usage_contest_exam_id_fkey",
        "ai_usage",
        "contest_exams",
        ["contest_exam_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ai_usage_contest_exam_id_fkey", "ai_usage", type_="foreignkey")
    op.drop_column("ai_usage", "contest_exam_id")
    op.execute("DELETE FROM questions WHERE id IN (SELECT question_id FROM contest_exam_questions)")
    op.drop_table("contest_exam_questions")
    op.drop_index("idx_contest_exams_status", table_name="contest_exams")
    op.drop_table("contest_exams")
    op.execute("DELETE FROM subjects WHERE area_id = 5")
    op.execute("DELETE FROM knowledge_areas WHERE id = 5")
    op.drop_constraint("answer_or_annulled", "questions", type_="check")
    op.create_check_constraint(
        "answer_or_annulled", "questions", "is_annulled OR correct_option IS NOT NULL"
    )
    op.drop_column("questions", "is_published")
    op.drop_column("questions", "format")
    op.execute("DROP TYPE contest_exam_status")
    op.execute("DROP TYPE question_format")
