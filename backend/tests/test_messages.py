"""Boas-vindas automática após a assinatura e mensagem avulsa do admin (e-mail mockado)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.email.models import EmailLog
from app.jobs.models import Job
from app.modules.messages.service import paragraphs
from app.modules.users.models import User
from tests.helpers import auth, register
from tests.test_payments import _open_billing, _open_signup, admin_h, fake_mp  # noqa: F401

WELCOME = {
    "enabled": True,
    "subject": "Bem-vindo, {nome}!",
    "body": "Oi, {nome}!\n\nSua <b>assinatura</b> está ativa.\nBons estudos!",
    "delay_minutes": 10,
}


async def _email_jobs(db, type_: str):
    logs = (await db.scalars(select(EmailLog).where(EmailLog.type == type_))).all()
    jobs = (await db.scalars(select(Job).where(Job.queue == "email.send"))).all()
    ids = {log.id for log in logs}
    return logs, [j for j in jobs if j.payload.get("email_log_id") in ids]


async def _subscribe(client, fake_mp, h):  # noqa: F811
    checkout = (
        await client.post("/api/v1/payments/checkout", headers=h, json={"kind": "subscription"})
    ).json()
    fake_mp.pay(checkout["payment_id"], "10.00")
    resp = await client.post(f"/api/v1/payments/{checkout['payment_id']}/refresh", headers=h)
    assert resp.json()["status"] == "approved"


def test_paragrafos_trocam_nome_e_separam_blocos():
    assert paragraphs("Oi, {nome}!\n\nLinha 1\nLinha 2\n\n\n", "Ana Souza") == [
        ["Oi, Ana!"],
        ["Linha 1", "Linha 2"],
    ]


async def test_boas_vindas_desligada_por_padrao(client, db, admin_h, fake_mp):  # noqa: F811
    resp = await client.get("/api/v1/admin/messages/welcome", headers=admin_h)
    assert resp.status_code == 200 and resp.json()["enabled"] is False
    await _open_billing(client, admin_h)
    await _subscribe(client, fake_mp, await _open_signup(client))
    logs, _ = await _email_jobs(db, "welcome")
    assert logs == []


async def test_boas_vindas_depois_do_pagamento_uma_vez(client, db, admin_h, fake_mp):  # noqa: F811
    resp = await client.put("/api/v1/admin/messages/welcome", headers=admin_h, json=WELCOME)
    assert resp.status_code == 200, resp.text
    await _open_billing(client, admin_h)
    h = await _open_signup(client)  # nome "Pagante"
    await _subscribe(client, fake_mp, h)

    logs, jobs = await _email_jobs(db, "welcome")
    assert len(logs) == 1 and len(jobs) == 1
    payload = jobs[0].payload
    assert payload["subject"] == "Bem-vindo, Pagante!"
    assert "Oi, Pagante!" in payload["html"]
    assert "&lt;b&gt;assinatura&lt;/b&gt;" in payload["html"]  # texto do admin é escapado
    assert "<br />" in payload["html"]
    # sai depois do "pagamento confirmado"
    approved, approved_jobs = await _email_jobs(db, "payment_approved")
    assert jobs[0].run_after - approved_jobs[0].run_after >= timedelta(minutes=9)

    # renovação não manda de novo
    await _subscribe(client, fake_mp, h)
    logs, _ = await _email_jobs(db, "welcome")
    assert len(logs) == 1


async def test_admin_envia_mensagem_para_uma_conta(client, db, admin_h):  # noqa: F811
    tokens = await register(client, email="aluno.msg@example.com", name="Bruno Lima")
    student = await db.scalar(select(User).where(User.email == "aluno.msg@example.com"))
    body = {"subject": "Olá, {nome}", "body": "Vimos que você assinou. Conte com a gente!"}

    # aluno não pode
    resp = await client.post(
        f"/api/v1/admin/users/{student.id}/message",
        headers=auth(tokens["access_token"]),
        json=body,
    )
    assert resp.status_code == 403

    resp = await client.post(
        f"/api/v1/admin/users/{student.id}/message", headers=admin_h, json=body
    )
    assert resp.status_code == 202, resp.text
    assert resp.json() == {"queued": True}  # a resposta não devolve dados da conta
    logs, jobs = await _email_jobs(db, "admin_message")
    assert len(logs) == 1 and logs[0].to_email == "aluno.msg@example.com"
    assert jobs[0].payload["subject"] == "Olá, Bruno"
    assert "Conte com a gente!" in jobs[0].payload["html"]
    assert jobs[0].run_after <= datetime.now(UTC) + timedelta(seconds=5)

    # pode mandar mais de uma vez (sem dedupe)
    await client.post(f"/api/v1/admin/users/{student.id}/message", headers=admin_h, json=body)
    logs, _ = await _email_jobs(db, "admin_message")
    assert len(logs) == 2

    resp = await client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/message", headers=admin_h, json=body
    )
    assert resp.status_code == 404

    await db.execute(
        update(User).where(User.id == student.id).values(disabled_at=datetime.now(UTC))
    )
    await db.commit()
    resp = await client.post(
        f"/api/v1/admin/users/{student.id}/message", headers=admin_h, json=body
    )
    assert resp.status_code == 409

    resp = await client.post(
        f"/api/v1/admin/users/{student.id}/message",
        headers=admin_h,
        json={"subject": "  ", "body": "x"},
    )
    assert resp.status_code == 422


async def test_teste_da_boas_vindas_vai_para_o_admin(client, db, admin_h):  # noqa: F811
    resp = await client.post(
        "/api/v1/admin/messages/welcome/test",
        headers=admin_h,
        json={"subject": WELCOME["subject"], "body": WELCOME["body"]},
    )
    assert resp.status_code == 202
    logs, jobs = await _email_jobs(db, "welcome_test")
    assert logs[0].to_email == "admin@example.com"
    assert jobs[0].payload["subject"] == "Bem-vindo, Admin!"
