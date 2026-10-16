"""Painel admin: configurações, chaves de IA criptografadas, eventos e job cancelado

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'cancelled'")
    op.add_column(
        "ai_usage",
        sa.Column("provider", sa.Text(), server_default=sa.text("'anthropic'"), nullable=False),
    )
    op.execute("UPDATE ai_usage SET provider = 'fake' WHERE model = 'fake'")
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name="app_settings_updated_by_fkey", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("key", name="app_settings_pkey"),
    )
    op.create_table(
        "ai_credentials",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_hint", sa.Text(), nullable=False),
        sa.Column("last_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provider IN ('anthropic','openai','google')", name="ai_credentials_provider_check"
        ),
        sa.PrimaryKeyConstraint("provider", name="ai_credentials_pkey"),
    )
    op.create_table(
        "system_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="system_events_pkey"),
    )
    op.create_index("idx_system_events_time", "system_events", [sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_system_events_time", table_name="system_events")
    op.drop_table("system_events")
    op.drop_table("ai_credentials")
    op.drop_table("app_settings")
    op.drop_column("ai_usage", "provider")
    # O Postgres não remove valores de enum: jobs cancelados voltam a "failed".
    op.execute("UPDATE jobs SET status = 'failed' WHERE status = 'cancelled'")
