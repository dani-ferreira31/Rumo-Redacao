"""Assinatura e doações pelo Mercado Pago (cliente falso: nenhuma chamada real)."""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.enums import UserRole
from app.email.models import EmailLog
from app.modules.payments import mercadopago as mp
from app.modules.payments.models import Payment
from app.modules.payments.service import send_renewal_reminders
from app.modules.users.models import User
from tests.helpers import auth, register, register_payload


class FakeMP:
    def __init__(self):
        self.preferences: list[dict] = []
        self.payments: dict[str, mp.MPPayment] = {}

    async def create_preference(self, body, idempotency_key):
        self.preferences.append(body)
        n = len(self.preferences)
        return mp.Preference(id=f"pref-{n}", checkout_url=f"https://mp.test/checkout/{n}")

    async def get_payment(self, payment_id):
        return self.payments[payment_id]

    async def search_by_reference(self, reference):
        return [p for p in self.payments.values() if p.external_reference == reference]

    def pay(self, reference, amount, status="approved", mp_id=None):
        mp_id = mp_id or f"{len(self.payments) + 1000}"
        self.payments[mp_id] = mp.MPPayment(
            id=mp_id,
            status=status,
            external_reference=reference,
            amount=Decimal(amount),
            method="pix",
        )
        return mp_id


@pytest.fixture
def fake_mp():
    fake = FakeMP()
    mp.set_client(fake)
    yield fake
    mp.set_client(None)


@pytest.fixture
async def admin_h(client, db):
    tokens = await register(client, email="admin@example.com", name="Admin")
    await db.execute(
        update(User).where(User.email == "admin@example.com").values(role=UserRole.admin)
    )
    await db.commit()
    return auth(tokens["access_token"])


async def _open_billing(client, admin_h, **overrides):
    body = {"enabled": True, "price_brl": 10, "period_days": 30, "donations_enabled": True}
    body.update(overrides)
    resp = await client.put("/api/v1/admin/payments/settings", headers=admin_h, json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _open_signup(client, email="pagante@example.com"):
    payload = register_payload(email=email, name="Pagante")
    del payload["invite_code"]
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return auth(resp.json()["access_token"])


async def test_cadastro_pago_exige_mercado_pago_configurado(client, admin_h):
    assert (await client.get("/api/v1/billing")).json()["enabled"] is False
    resp = await client.put(
        "/api/v1/admin/payments/settings",
        headers=admin_h,
        json={"enabled": True, "price_brl": 10, "period_days": 30, "donations_enabled": True},
    )
    assert resp.status_code == 409


async def test_assinatura_libera_30_dias_e_so_uma_vez(client, db, admin_h, fake_mp):
    await _open_billing(client, admin_h)
    info = (await client.get("/api/v1/billing")).json()
    assert info["enabled"] is True and info["price_brl"] == 10

    h = await _open_signup(client)
    me = (await client.get("/api/v1/me", headers=h)).json()
    assert me["access_active"] is False and me["free_access"] is False
    for path in ("/api/v1/essays", "/api/v1/questions", "/api/v1/study-plans"):
        resp = await client.get(path, headers=h)
        assert resp.status_code == 402, path
        assert resp.json()["error"]["code"] == "payment_required"

    resp = await client.post("/api/v1/payments/checkout", headers=h, json={"kind": "subscription"})
    assert resp.status_code == 200, resp.text
    checkout = resp.json()
    assert checkout["checkout_url"] == "https://mp.test/checkout/1"
    pref = fake_mp.preferences[0]
    assert pref["items"][0]["unit_price"] == 10.0
    assert pref["external_reference"] == checkout["payment_id"]
    assert pref["back_urls"]["success"].endswith(f"/assinatura?pagamento={checkout['payment_id']}")
    assert "notification_url" not in pref  # API_URL de teste não é https

    # voltou do Mercado Pago, mas o PIX ainda não caiu
    fake_mp.pay(checkout["payment_id"], "10.00", status="pending")
    path = f"/api/v1/payments/{checkout['payment_id']}/refresh"
    assert (await client.post(path, headers=h)).json()["status"] == "pending"
    assert (await client.get("/api/v1/me", headers=h)).json()["access_active"] is False

    fake_mp.pay(checkout["payment_id"], "10.00", status="approved")
    assert (await client.post(path, headers=h)).json()["status"] == "approved"
    me = (await client.get("/api/v1/me", headers=h)).json()
    assert me["access_active"] is True
    until = datetime.fromisoformat(me["paid_until"])
    assert timedelta(days=29, hours=23) < until - datetime.now(UTC) <= timedelta(days=30)
    assert (await client.get("/api/v1/essays", headers=h)).status_code == 200

    # consultar de novo não soma mais 30 dias
    await client.post(path, headers=h)
    again = (await client.get("/api/v1/me", headers=h)).json()
    assert again["paid_until"] == me["paid_until"]
    emails = (await db.scalars(select(EmailLog).where(EmailLog.type == "payment_approved"))).all()
    assert len(emails) == 1

    # renovar antes de vencer soma ao fim do período atual
    second = (
        await client.post("/api/v1/payments/checkout", headers=h, json={"kind": "subscription"})
    ).json()
    fake_mp.pay(second["payment_id"], "10.00")
    await client.post(f"/api/v1/payments/{second['payment_id']}/refresh", headers=h)
    renewed = datetime.fromisoformat(
        (await client.get("/api/v1/me", headers=h)).json()["paid_until"]
    )
    assert renewed - until == timedelta(days=30)


async def test_convidado_nao_paga_mesmo_com_cadastro_pago(client, admin_h, fake_mp):
    await _open_billing(client, admin_h)
    h = auth((await register(client, email="convidado@example.com"))["access_token"])
    assert (await client.get("/api/v1/me", headers=h)).json()["access_active"] is True
    assert (await client.get("/api/v1/essays", headers=h)).status_code == 200


async def test_webhook_confere_assinatura_e_valor(client, db, admin_h, fake_mp, monkeypatch):
    await _open_billing(client, admin_h)
    h = await _open_signup(client)
    checkout = (
        await client.post("/api/v1/payments/checkout", headers=h, json={"kind": "subscription"})
    ).json()
    secret = "segredo-webhook"
    monkeypatch.setattr(get_settings(), "mercadopago_webhook_secret", secret)

    def signed(data_id, request_id="req-1", ts="1700000000"):
        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
        return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}

    # valor menor que o cobrado: não libera
    low = fake_mp.pay(checkout["payment_id"], "1.00")
    url = f"/api/v1/payments/webhook/mercadopago?type=payment&data.id={low}"
    assert (await client.post(url, headers={"x-signature": "ts=1,v1=errado"})).status_code == 401
    assert (await client.post(url, headers=signed(low))).status_code == 200
    assert (await client.get("/api/v1/me", headers=h)).json()["access_active"] is False

    ok = fake_mp.pay(checkout["payment_id"], "10.00")
    url = f"/api/v1/payments/webhook/mercadopago?type=payment&data.id={ok}"
    assert (await client.post(url, headers=signed(ok))).status_code == 200
    assert (await client.get("/api/v1/me", headers=h)).json()["access_active"] is True

    # estorno devolve os dias
    fake_mp.payments[ok].status = "refunded"
    assert (await client.post(url, headers=signed(ok))).status_code == 200
    assert (await client.get("/api/v1/me", headers=h)).json()["access_active"] is False
    payment = await db.get(Payment, uuid.UUID(checkout["payment_id"]))
    await db.refresh(payment)
    assert payment.status == "refunded"

    # avisos de outros tipos são ignorados
    resp = await client.post("/api/v1/payments/webhook/mercadopago?type=merchant_order&data.id=1")
    assert resp.status_code == 200


async def test_doacao_para_qualquer_usuario(client, db, admin_h, fake_mp):
    await _open_billing(client, admin_h, enabled=False)  # doação não depende do cadastro pago
    h = auth((await register(client, email="doador@example.com"))["access_token"])
    for amount in ("1.00", "1500"):
        resp = await client.post(
            "/api/v1/payments/checkout", headers=h, json={"kind": "donation", "amount": amount}
        )
        assert resp.json()["error"]["code"] == "invalid_amount"
    checkout = (
        await client.post(
            "/api/v1/payments/checkout", headers=h, json={"kind": "donation", "amount": "25.5"}
        )
    ).json()
    assert fake_mp.preferences[-1]["items"][0]["unit_price"] == 25.5
    assert fake_mp.preferences[-1]["back_urls"]["success"].startswith("http://app.test/apoiar?")
    fake_mp.pay(checkout["payment_id"], "25.50")
    await client.post(f"/api/v1/payments/{checkout['payment_id']}/refresh", headers=h)

    user = await db.scalar(select(User).where(User.email == "doador@example.com"))
    assert user.paid_until is None  # doação não mexe no acesso
    assert await db.scalar(select(EmailLog.id).where(EmailLog.type == "donation_thanks"))

    report = (await client.get("/api/v1/admin/payments", headers=admin_h)).json()
    assert report["summary"]["month_donations_brl"] == "25.50"
    assert report["payments"][0]["user_email"] == "doador@example.com"

    await _open_billing(client, admin_h, enabled=False, donations_enabled=False)
    resp = await client.post(
        "/api/v1/payments/checkout", headers=h, json={"kind": "donation", "amount": "10"}
    )
    assert resp.json()["error"]["code"] == "donations_disabled"


async def test_admin_libera_acesso_de_cortesia(client, db, admin_h, fake_mp):
    await _open_billing(client, admin_h)
    h = await _open_signup(client, email="cortesia@example.com")
    user = await db.scalar(select(User).where(User.email == "cortesia@example.com"))
    resp = await client.patch(
        f"/api/v1/admin/users/{user.id}", headers=admin_h, json={"free_access": True}
    )
    assert resp.json()["free_access"] is True
    assert (await client.get("/api/v1/essays", headers=h)).status_code == 200


async def test_lembrete_de_renovacao_uma_vez(client, db, admin_h, fake_mp):
    await _open_billing(client, admin_h)
    await _open_signup(client, email="vence@example.com")
    await db.execute(
        update(User)
        .where(User.email == "vence@example.com")
        .values(paid_until=datetime.now(UTC) + timedelta(days=2))
    )
    await db.commit()
    await send_renewal_reminders(db)
    await send_renewal_reminders(db)
    logs = (
        await db.scalars(select(EmailLog).where(EmailLog.type == "subscription_expiring"))
    ).all()
    assert len(logs) == 1
