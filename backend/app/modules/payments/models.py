import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import PaymentKind, PaymentStatus, pg_enum


class Payment(Base):
    """Uma cobrança no Mercado Pago (assinatura ou doação).

    O `id` vai como `external_reference` na preferência: é assim que a
    notificação do Mercado Pago encontra a linha certa.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="payments_amount_check"),
        Index("idx_payments_user", "user_id", text("created_at DESC")),
        Index("idx_payments_created", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    kind: Mapped[PaymentKind] = mapped_column(pg_enum(PaymentKind, "payment_kind"))
    status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"), server_default=text("'pending'")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # dias de acesso que a assinatura libera (None em doações)
    period_days: Mapped[int | None] = mapped_column(SmallInteger)
    provider: Mapped[str] = mapped_column(Text, server_default=text("'mercadopago'"))
    preference_id: Mapped[str | None] = mapped_column(Text)
    provider_payment_id: Mapped[str | None] = mapped_column(Text, unique=True)
    method: Mapped[str | None] = mapped_column(Text)  # pix, credit_card...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
