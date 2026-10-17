"""Assinatura (acesso por período) e doações pelo Mercado Pago (Checkout Pro).

Fluxo: o app cria a cobrança (`payments`, status pending) e uma preferência no
Mercado Pago; o usuário paga na página do Mercado Pago (PIX ou cartão). A
confirmação chega pela notificação (webhook) ou quando o usuário volta ao app
(consulta direta). Em ambos os casos o pagamento é reconsultado na API do
Mercado Pago: o app nunca confia só no que veio na notificação.
"""

import logging
import uuid
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import PaymentKind, PaymentStatus, UserRole
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.email.service import queue_email
from app.modules.payments import mercadopago as mp
from app.modules.payments.access import access_ok, billing
from app.modules.payments.models import Payment
from app.modules.payments.schemas import (
    DONATION_MAX,
    DONATION_MIN,
    AdminPaymentOut,
    AdminPaymentsOut,
    BillingAdminOut,
    BillingPublic,
    BillingSettings,
    CheckoutIn,
    CheckoutOut,
    PaymentOut,
    PaymentSummary,
    SubscriptionOut,
)
from app.modules.system.settings import log_event, set_setting
from app.modules.users.models import User

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Sao_Paulo")
RENEWAL_NOTICE = timedelta(days=3)

# status do Mercado Pago -> status no app
STATUS = {
    "approved": PaymentStatus.approved,
    "rejected": PaymentStatus.rejected,
    "cancelled": PaymentStatus.cancelled,
    "refunded": PaymentStatus.refunded,
    "charged_back": PaymentStatus.refunded,
}


def _brl(value: Decimal | float) -> str:
    return f"{Decimal(str(value)):.2f}".replace(".", ",")


def _local_date(dt) -> str:
    return dt.astimezone(TZ).strftime("%d/%m/%Y")


def _out(p: Payment) -> PaymentOut:
    return PaymentOut(
        id=p.id,
        kind=p.kind,
        status=p.status,
        amount=p.amount,
        method=p.method,
        created_at=p.created_at,
        paid_at=p.paid_at,
    )


# ---- público / usuário ----------------------------------------------------------------


async def public_billing(session: AsyncSession) -> BillingPublic:
    b = await billing(session)
    on = mp.configured()
    return BillingPublic(
        enabled=bool(b["enabled"]) and on,
        price_brl=float(b["price_brl"]),
        period_days=int(b["period_days"]),
        donations_enabled=bool(b["donations_enabled"]) and on,
    )


async def subscription(session: AsyncSession, user: User) -> SubscriptionOut:
    b = await billing(session)
    rows = await session.scalars(
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(20)
    )
    return SubscriptionOut(
        active=access_ok(user, bool(b["enabled"])),
        free_access=user.free_access or user.role != UserRole.student,
        paid_until=user.paid_until,
        price_brl=float(b["price_brl"]),
        period_days=int(b["period_days"]),
        payments=[_out(p) for p in rows],
    )


async def checkout(session: AsyncSession, user: User, data: CheckoutIn) -> CheckoutOut:
    if not mp.configured():
        raise AppError("payments_unavailable", "Pagamentos indisponíveis no momento.", 503)
    b = await billing(session)
    settings = get_settings()
    if data.kind == PaymentKind.subscription:
        if not b["enabled"]:
            raise AppError("billing_disabled", "A assinatura não está disponível agora.", 409)
        amount = Decimal(str(b["price_brl"])).quantize(Decimal("0.01"))
        period = int(b["period_days"])
        title = f"Rumo1000: assinatura de {period} dias"
        page = "assinatura"
    else:
        if not b["donations_enabled"]:
            raise AppError("donations_disabled", "As doações não estão disponíveis agora.", 409)
        if data.amount is None:
            raise AppError("invalid_amount", "Informe o valor da doação.", 422)
        amount = data.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if not DONATION_MIN <= amount <= DONATION_MAX:
            raise AppError(
                "invalid_amount",
                f"A doação vai de R$ {_brl(DONATION_MIN)} a R$ {_brl(DONATION_MAX)}.",
                422,
            )
        period = None
        title = "Rumo1000: doação"
        page = "apoiar"

    payment = Payment(user_id=user.id, kind=data.kind, amount=amount, period_days=period)
    session.add(payment)
    await session.flush()

    back = f"{settings.app_url}/{page}?pagamento={payment.id}"
    body: dict = {
        "items": [
            {
                "id": data.kind.value,
                "title": title,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(amount),
            }
        ],
        "payer": {"email": user.email, "name": user.name},
        "external_reference": str(payment.id),
        "back_urls": {"success": back, "pending": back, "failure": back},
        "statement_descriptor": "RUMO1000",
    }
    # o Mercado Pago só aceita retorno automático e notificação em endereços https
    if settings.app_url.startswith("https://"):
        body["auto_return"] = "approved"
    if settings.api_url.startswith("https://"):
        body["notification_url"] = f"{settings.api_url}/api/v1/payments/webhook/mercadopago"
    try:
        pref = await mp.get_client().create_preference(body, idempotency_key=str(payment.id))
    except mp.MercadoPagoError as exc:
        logger.error("mercadopago_preference_failed", extra={"extra_fields": {"error": str(exc)}})
        raise AppError(
            "payments_unavailable",
            "Não foi possível abrir o pagamento agora. Tente de novo em instantes.",
            502,
        ) from exc
    payment.preference_id = pref.id
    await session.commit()
    return CheckoutOut(payment_id=payment.id, checkout_url=pref.checkout_url)


async def _apply(session: AsyncSession, payment: Payment, info: mp.MPPayment) -> None:
    """Aplica o status do Mercado Pago. Idempotente: libera o acesso uma vez só."""
    new = STATUS.get(info.status, PaymentStatus.pending)
    was_approved = payment.status == PaymentStatus.approved
    if new == PaymentStatus.pending or (was_approved and new == PaymentStatus.approved):
        return
    if was_approved and new not in (PaymentStatus.refunded, PaymentStatus.cancelled):
        return  # depois de aprovado, só estorno muda alguma coisa

    user = await session.get(User, payment.user_id) if payment.user_id else None
    now = utcnow()
    payment.provider_payment_id = info.id
    payment.method = info.method

    if new == PaymentStatus.approved:
        if info.amount < payment.amount:
            logger.warning(
                "payment_amount_mismatch",
                extra={"extra_fields": {"payment_id": str(payment.id), "mp_id": info.id}},
            )
            return
        payment.status = PaymentStatus.approved
        payment.paid_at = now
        if user and payment.kind == PaymentKind.subscription:
            start = max(now, user.paid_until or now)
            user.paid_until = start + timedelta(days=payment.period_days or 30)
            log_event(session, "payment", f"Assinatura paga: R$ {_brl(payment.amount)}")
            await queue_email(
                session,
                to=user.email,
                type="payment_approved",
                subject="Pagamento confirmado: sua assinatura do Rumo1000 está ativa",
                template="payment_approved.html",
                context={
                    "name": user.name,
                    "amount": _brl(payment.amount),
                    "until": _local_date(user.paid_until),
                    "url": f"{get_settings().app_url}/painel",
                },
                user_id=user.id,
                dedupe_key=f"payment:{payment.id}",
            )
        elif user:
            log_event(session, "payment", f"Doação recebida: R$ {_brl(payment.amount)}")
            await queue_email(
                session,
                to=user.email,
                type="donation_thanks",
                subject="Obrigado pela sua doação ao Rumo1000!",
                template="donation_thanks.html",
                context={
                    "name": user.name,
                    "amount": _brl(payment.amount),
                    "url": f"{get_settings().app_url}/painel",
                },
                user_id=user.id,
                dedupe_key=f"payment:{payment.id}",
            )
    else:
        payment.status = new
        # estorno de assinatura: devolve os dias que ela tinha liberado
        if was_approved and user and payment.kind == PaymentKind.subscription and user.paid_until:
            user.paid_until -= timedelta(days=payment.period_days or 30)
            log_event(session, "payment", f"Assinatura estornada: R$ {_brl(payment.amount)}")
    await session.commit()


async def handle_notification(session: AsyncSession, mp_payment_id: str) -> None:
    info = await mp.get_client().get_payment(mp_payment_id)
    try:
        payment_id = uuid.UUID(info.external_reference or "")
    except ValueError:
        return  # pagamento que não saiu do app
    payment = await session.get(Payment, payment_id)
    if payment is not None:
        await _apply(session, payment, info)


async def refresh(session: AsyncSession, user: User, payment_id: uuid.UUID) -> PaymentOut:
    """Consulta o Mercado Pago na volta do usuário (cobre atraso ou falta do webhook)."""
    payment = await session.get(Payment, payment_id)
    if payment is None or payment.user_id != user.id:
        raise NotFoundError("Pagamento não encontrado.")
    if payment.status == PaymentStatus.pending and mp.configured():
        try:
            found = await mp.get_client().search_by_reference(str(payment.id))
        except mp.MercadoPagoError as exc:
            logger.warning("mercadopago_search_failed", extra={"extra_fields": {"error": str(exc)}})
            found = []
        approved = [f for f in found if f.status == "approved"]
        if approved or found:
            await _apply(session, payment, (approved or found)[0])
            await session.refresh(payment)
    return _out(payment)


async def send_renewal_reminders(session: AsyncSession) -> None:
    """E-mail 3 dias antes de a assinatura vencer (uma vez por período)."""
    b = await billing(session)
    if not b["enabled"]:
        return
    now = utcnow()
    users = await session.scalars(
        select(User).where(
            User.free_access.is_(False),
            User.disabled_at.is_(None),
            User.paid_until > now,
            User.paid_until <= now + RENEWAL_NOTICE,
        )
    )
    for user in users:
        await queue_email(
            session,
            to=user.email,
            type="subscription_expiring",
            subject="Sua assinatura do Rumo1000 vence em breve",
            template="subscription_expiring.html",
            context={
                "name": user.name,
                "until": _local_date(user.paid_until),
                "price": _brl(b["price_brl"]),
                "url": f"{get_settings().app_url}/assinatura",
            },
            user_id=user.id,
            dedupe_key=f"renewal:{user.id}:{user.paid_until.date().isoformat()}",
        )
    await session.commit()


# ---- admin ----------------------------------------------------------------------------


async def admin_settings(session: AsyncSession) -> BillingAdminOut:
    b = await billing(session)
    return BillingAdminOut(
        **BillingSettings(**b).model_dump(),
        mercadopago_configured=mp.configured(),
        webhook_secret_configured=bool(get_settings().mercadopago_webhook_secret),
    )


async def set_admin_settings(
    session: AsyncSession, admin: User, data: BillingSettings
) -> BillingAdminOut:
    if data.enabled and not mp.configured():
        raise AppError(
            "payments_unavailable",
            "Configure MERCADOPAGO_ACCESS_TOKEN no servidor antes de abrir o cadastro pago.",
            409,
        )
    await set_setting(session, "billing", data.model_dump(), admin.id)
    state = "aberto com assinatura" if data.enabled else "só por convite"
    log_event(
        session,
        "payment",
        f"Cadastro {state}; assinatura R$ {_brl(data.price_brl)} por {data.period_days} dias; "
        f"doações {'ligadas' if data.donations_enabled else 'desligadas'}",
    )
    await session.commit()
    return await admin_settings(session)


async def admin_payments(session: AsyncSession, limit: int = 100) -> AdminPaymentsOut:
    now = utcnow()
    local = now.astimezone(TZ)
    month = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def total(kind: PaymentKind) -> Decimal:
        value = await session.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.kind == kind,
                Payment.status == PaymentStatus.approved,
                Payment.paid_at >= month,
            )
        )
        return Decimal(value or 0)

    active = await session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.free_access.is_(False), User.paid_until > now)
    )
    pending = await session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.status == PaymentStatus.pending,
            Payment.created_at >= now - timedelta(days=1),
        )
    )
    rows = await session.execute(
        select(Payment, User.name, User.email)
        .outerjoin(User, User.id == Payment.user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    return AdminPaymentsOut(
        summary=PaymentSummary(
            month_subscriptions_brl=await total(PaymentKind.subscription),
            month_donations_brl=await total(PaymentKind.donation),
            active_subscribers=active or 0,
            pending=pending or 0,
        ),
        payments=[
            AdminPaymentOut(**_out(p).model_dump(), user_name=name, user_email=email)
            for p, name, email in rows
        ],
    )
