"""Convites, papel de professor, bloqueio de conta e provas do professor

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")
UUID_DEFAULT = sa.text("gen_random_uuid()")


def upgrade() -> None:
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'teacher' BEFORE 'admin'")

    op.create_table(
        "invites",
        sa.Column("id", sa.UUID(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("role", postgresql.ENUM(name="user_role", create_type=False), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.CheckConstraint("max_uses IS NULL OR max_uses > 0", name="invites_max_uses_check"),
        sa.CheckConstraint("role <> 'admin'", name="invites_role_check"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.add_column("users", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("invite_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "users_invite_id_fkey", "users", "invites", ["invite_id"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "assessments",
        sa.Column("id", sa.UUID(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("teacher_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("share_code", sa.Text(), nullable=False),
        sa.Column("is_open", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_code"),
    )
    op.create_index(
        "idx_assessments_teacher", "assessments", ["teacher_id", sa.text("created_at DESC")]
    )
    op.execute(
        "CREATE TRIGGER trg_assessments_updated BEFORE UPDATE ON assessments "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "assessment_questions",
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("assessment_id", "question_id"),
    )

    op.create_table(
        "assessment_attempts",
        sa.Column("id", sa.UUID(), server_default=UUID_DEFAULT, nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correct", sa.SmallInteger(), nullable=True),
        sa.Column("total", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "user_id"),
    )

    op.create_table(
        "assessment_answers",
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("selected_option", sa.CHAR(1), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["assessment_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("attempt_id", "question_id"),
    )


def downgrade() -> None:
    op.drop_table("assessment_answers")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_questions")
    op.drop_index("idx_assessments_teacher", table_name="assessments")
    op.drop_table("assessments")
    op.drop_constraint("users_invite_id_fkey", "users", type_="foreignkey")
    op.drop_column("users", "invite_id")
    op.drop_column("users", "disabled_at")
    op.drop_table("invites")
    # o valor 'teacher' do enum user_role fica (o Postgres não remove valores de enum)
