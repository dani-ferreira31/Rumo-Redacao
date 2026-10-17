import logging
import uuid

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user, require_admin
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.modules.payments import mercadopago as mp
from app.modules.payments import service
from app.modules.payments.schemas import (
    AdminPaymentsOut,
    BillingAdminOut,
    BillingPublic,
    BillingSettings,
    CheckoutIn,
    CheckoutOut,
    PaymentOut,
    SubscriptionOut,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


@router.get("/billing", response_model=BillingPublic)
async def billing_info(session: AsyncSession = Depends(get_session)):
    """Público: se o cadastro pago está aberto, o preço e se há doações."""
    return await service.public_billing(session)


@router.get("/me/subscription", response_model=SubscriptionOut)
async def my_subscription(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await service.subscription(session, user)


@router.post("/payments/checkout", response_model=CheckoutOut)
@limiter.limit("10/minute")
async def checkout(
    request: Request,
    data: CheckoutIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Cria a cobrança e devolve o link da página de pagamento do Mercado Pago."""
    return await service.checkout(session, user, data)


@router.post("/payments/{payment_id}/refresh", response_model=PaymentOut)
@limiter.limit("30/minute")
async def refresh_payment(
    request: Request,
    payment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Na volta do Mercado Pago: confere o pagamento direto na API."""
    return await service.refresh(session, user, payment_id)


@router.post("/payments/webhook/mercadopago", status_code=status.HTTP_200_OK)
async def mercadopago_webhook(
    request: Request,
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    """Notificação do Mercado Pago. O pagamento é sempre reconsultado na API."""
    params = request.query_params
    kind = params.get("type") or params.get("topic")
    data_id = params.get("data.id") or params.get("id")
    if kind != "payment" or not data_id:
        return Response(status_code=status.HTTP_200_OK)  # outros avisos não interessam
    if not mp.valid_signature(x_signature, x_request_id, data_id):
        raise AppError("invalid_signature", "Assinatura da notificação inválida.", 401)
    try:
        await service.handle_notification(session, data_id)
    except mp.MercadoPagoError as exc:
        # 5xx: o Mercado Pago reenvia a notificação mais tarde
        logger.warning("mercadopago_webhook_failed", extra={"extra_fields": {"error": str(exc)}})
        raise AppError("payments_unavailable", "Falha ao consultar o pagamento.", 502) from exc
    return Response(status_code=status.HTTP_200_OK)


# ---- admin ----------------------------------------------------------------------------


@router.get("/admin/payments/settings", response_model=BillingAdminOut)
async def get_billing_settings(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    return await service.admin_settings(session)


@router.put("/admin/payments/settings", response_model=BillingAdminOut)
async def put_billing_settings(
    data: BillingSettings,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    return await service.set_admin_settings(session, admin, data)


@router.get("/admin/payments", response_model=AdminPaymentsOut)
async def list_payments(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    """Receita do mês e os últimos pagamentos (com nome e e-mail de quem pagou)."""
    return await service.admin_payments(session)
