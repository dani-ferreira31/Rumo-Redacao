"""Pagamentos (Mercado Pago): assinatura e doações; acesso livre para convidados

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("free_access", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("users", sa.Column("paid_until", sa.DateTime(timezone=True), nullable=True))
    # contas que já existem (admin, convidados) continuam sem pagar
    op.execute("UPDATE users SET free_access = true")

    op.execute("CREATE TYPE payment_kind AS ENUM ('subscription', 'donation')")
    op.execute(
        "CREATE TYPE payment_status AS ENUM "
        "('pending', 'approved', 'rejected', 'cancelled', 'refunded')"
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("kind", postgresql.ENUM(name="payment_kind", create_type=False), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(name="payment_status", create_type=False),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("period_days", sa.SmallInteger(), nullable=True),
        sa.Column("provider", sa.Text(), server_default=sa.text("'mercadopago'"), nullable=False),
        sa.Column("preference_id", sa.Text(), nullable=True),
        sa.Column("provider_payment_id", sa.Text(), nullable=True),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="payments_amount_check"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_payment_id"),
    )
    op.create_index("idx_payments_user", "payments", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_payments_created", "payments", [sa.text("created_at DESC")])
    op.execute(
        "CREATE TRIGGER trg_payments_updated BEFORE UPDATE ON payments "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.execute("DROP TYPE payment_status")
    op.execute("DROP TYPE payment_kind")
    op.drop_column("users", "paid_until")
    op.drop_column("users", "free_access")
