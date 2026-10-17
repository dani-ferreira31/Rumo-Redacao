"""Cliente mínimo da API do Mercado Pago (Checkout Pro).

Só três chamadas: criar a preferência (página de pagamento com PIX e cartão),
consultar um pagamento e buscar pagamentos de uma cobrança nossa. Nos testes,
`set_client` troca por um falso.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

API = "https://api.mercadopago.com"
TIMEOUT = 20.0


class MercadoPagoError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Preference:
    id: str
    checkout_url: str


@dataclass
class MPPayment:
    id: str
    status: str  # approved, pending, in_process, rejected, cancelled, refunded, charged_back...
    external_reference: str | None
    amount: Decimal
    method: str | None


class Client(Protocol):
    async def create_preference(self, body: dict[str, Any], idempotency_key: str) -> Preference: ...
    async def get_payment(self, payment_id: str) -> MPPayment: ...
    async def search_by_reference(self, reference: str) -> list[MPPayment]: ...


def _payment(data: dict[str, Any]) -> MPPayment:
    return MPPayment(
        id=str(data["id"]),
        status=data.get("status") or "pending",
        external_reference=data.get("external_reference"),
        amount=Decimal(str(data.get("transaction_amount") or 0)),
        method=data.get("payment_type_id") or data.get("payment_method_id"),
    )


class HttpClient:
    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}"}

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(base_url=API, timeout=TIMEOUT) as http:
            resp = await http.request(method, path, headers=headers, **kwargs)
        if resp.status_code >= 400:
            # o corpo traz a mensagem do Mercado Pago, nunca o token
            raise MercadoPagoError(f"{resp.status_code}: {resp.text[:300]}", resp.status_code)
        return resp.json()

    async def create_preference(self, body: dict[str, Any], idempotency_key: str) -> Preference:
        data = await self._request(
            "POST",
            "/checkout/preferences",
            json=body,
            headers={"X-Idempotency-Key": idempotency_key},
        )
        return Preference(id=data["id"], checkout_url=data["init_point"])

    async def get_payment(self, payment_id: str) -> MPPayment:
        return _payment(await self._request("GET", f"/v1/payments/{payment_id}"))

    async def search_by_reference(self, reference: str) -> list[MPPayment]:
        data = await self._request(
            "GET",
            "/v1/payments/search",
            params={
                "external_reference": reference,
                "sort": "date_created",
                "criteria": "desc",
            },
        )
        return [_payment(p) for p in data.get("results", [])]


_client: Client | None = None


def configured() -> bool:
    return _client is not None or bool(get_settings().mercadopago_access_token)


def get_client() -> Client:
    if _client is not None:
        return _client
    token = get_settings().mercadopago_access_token
    if not token:
        raise MercadoPagoError("MERCADOPAGO_ACCESS_TOKEN não configurado.")
    return HttpClient(token)


def set_client(client: Client | None) -> None:
    """Só para testes."""
    global _client
    _client = client


def valid_signature(x_signature: str | None, x_request_id: str | None, data_id: str) -> bool:
    """Confere a assinatura `x-signature` da notificação (HMAC-SHA256 com a chave secreta).

    Sem chave configurada, aceita: o pagamento é sempre reconsultado na API, então
    uma notificação falsa não libera nada sozinha.
    """
    secret = get_settings().mercadopago_webhook_secret
    if not secret:
        return True
    if not x_signature:
        return False
    parts = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = parts.get("ts"), parts.get("v1")
    if not ts or not v1:
        return False
    # o Mercado Pago omite do texto assinado as partes que não vieram na notificação
    manifest = f"id:{data_id.lower()};" if data_id else ""
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)
