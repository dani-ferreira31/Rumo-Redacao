import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.core.enums import PaymentKind, PaymentStatus

DONATION_MIN = Decimal("2.00")
DONATION_MAX = Decimal("1000.00")


class BillingPublic(BaseModel):
    """O que a tela de cadastro e a de assinatura precisam saber (público)."""

    enabled: bool = Field(description="Cadastro aberto com assinatura")
    price_brl: float
    period_days: int
    donations_enabled: bool
    donation_min: float = float(DONATION_MIN)
    donation_max: float = float(DONATION_MAX)


class BillingSettings(BaseModel):
    enabled: bool
    price_brl: float = Field(gt=0, le=10000)
    period_days: int = Field(ge=1, le=366)
    donations_enabled: bool


class BillingAdminOut(BillingSettings):
    mercadopago_configured: bool
    webhook_secret_configured: bool


class CheckoutIn(BaseModel):
    kind: PaymentKind
    amount: Decimal | None = Field(
        default=None, description="Só nas doações: valor em reais escolhido pelo usuário"
    )


class CheckoutOut(BaseModel):
    payment_id: uuid.UUID
    checkout_url: str


class PaymentOut(BaseModel):
    id: uuid.UUID
    kind: PaymentKind
    status: PaymentStatus
    amount: Decimal
    method: str | None
    created_at: datetime
    paid_at: datetime | None


class SubscriptionOut(BaseModel):
    active: bool
    free_access: bool
    paid_until: datetime | None
    price_brl: float
    period_days: int
    payments: list[PaymentOut]


class AdminPaymentOut(PaymentOut):
    user_name: str | None
    user_email: str | None


class PaymentSummary(BaseModel):
    month_subscriptions_brl: Decimal
    month_donations_brl: Decimal
    active_subscribers: int
    pending: int


class AdminPaymentsOut(BaseModel):
    summary: PaymentSummary
    payments: list[AdminPaymentOut]
