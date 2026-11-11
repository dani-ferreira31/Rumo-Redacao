"""Cadastro só por convite, papel definido pelo convite e gestão de contas pelo admin."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.enums import UserRole
from app.modules.invites.models import Invite
from app.modules.users.models import User
from tests.helpers import PASSWORD, auth, register, register_payload


@pytest.fixture
async def admin_h(client, db):
    tokens = await register(client, email="admin@example.com", name="Admin")
    await db.execute(
        update(User).where(User.email == "admin@example.com").values(role=UserRole.admin)
    )
    await db.commit()
    return auth(tokens["access_token"])


async def _create_invite(client, admin_h, **body):
    resp = await client.post("/api/v1/admin/invites", headers=admin_h, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---- cadastro ------------------------------------------------------------------------


async def test_cadastro_sem_convite_ou_com_convite_invalido(client):
    payload = register_payload()
    del payload["invite_code"]
    resp = await client.post("/api/v1/auth/register", json=payload)
    # com o cadastro pago desligado (padrão), sem convite não entra
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "invite_required"

    resp = await client.post("/api/v1/auth/register", json=register_payload(invite_code="xpto"))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "invite_invalid"


async def test_convite_invalido_nao_revela_email_cadastrado(client):
    await register(client)
    resp = await client.post("/api/v1/auth/register", json=register_payload(invite_code="xpto"))
    assert resp.json()["error"]["code"] == "invite_invalid"


async def test_convite_de_professor_cria_conta_de_professor(client, db, admin_h):
    inv = await _create_invite(client, admin_h, role="teacher", note="Prof. de redação")
    assert inv["url"].endswith(f"/cadastro?convite={inv['code']}")
    assert inv["status"] == "active"

    info = await client.get(f"/api/v1/invites/{inv['code']}")
    assert info.json() == {"role": "teacher", "expires_at": None}

    await register(client, email="prof@example.com", invite_code=inv["code"])
    user = await db.scalar(select(User).where(User.email == "prof@example.com"))
    assert user.role == UserRole.teacher
    assert str(user.invite_id) == inv["id"]

    listed = (await client.get("/api/v1/admin/invites", headers=admin_h)).json()
    assert next(i for i in listed if i["id"] == inv["id"])["uses"] == 1


async def test_convite_nao_pode_ser_de_admin(client, admin_h):
    resp = await client.post("/api/v1/admin/invites", headers=admin_h, json={"role": "admin"})
    assert resp.status_code == 422


async def test_limite_de_usos_validade_e_revogacao(client, db, admin_h):
    once = await _create_invite(client, admin_h, role="student", max_uses=1)
    await register(client, email="a1@example.com", invite_code=once["code"])
    resp = await client.post(
        "/api/v1/auth/register",
        json=register_payload(email="a2@example.com", invite_code=once["code"]),
    )
    assert resp.status_code == 403
    assert (await client.get(f"/api/v1/invites/{once['code']}")).status_code == 403

    week = await _create_invite(client, admin_h, role="student", expires_in_days=7)
    await db.execute(
        update(Invite)
        .where(Invite.code == week["code"])
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db.commit()
    resp = await client.post(
        "/api/v1/auth/register",
        json=register_payload(email="a3@example.com", invite_code=week["code"]),
    )
    assert resp.status_code == 403

    open_ = await _create_invite(client, admin_h, role="student")
    revoked = await client.post(f"/api/v1/admin/invites/{open_['id']}/revoke", headers=admin_h)
    assert revoked.json()["status"] == "revoked"
    resp = await client.post(
        "/api/v1/auth/register",
        json=register_payload(email="a4@example.com", invite_code=open_["code"]),
    )
    assert resp.status_code == 403


async def test_convites_exigem_admin(client):
    h = auth((await register(client))["access_token"])
    assert (await client.get("/api/v1/admin/invites", headers=h)).status_code == 403
    assert (await client.get("/api/v1/admin/users", headers=h)).status_code == 403


# ---- gestão de contas ----------------------------------------------------------------


async def test_admin_lista_e_busca_usuarios(client, admin_h):
    await register(client, email="joana@example.com", name="Joana Lima")
    await register(client, email="pedro@example.com", name="Pedro Alves")

    page = (await client.get("/api/v1/admin/users", headers=admin_h)).json()
    assert page["total"] == 3
    assert {"name", "email", "role", "disabled_at", "created_at"} <= set(page["items"][0])

    found = (await client.get("/api/v1/admin/users?q=joana", headers=admin_h)).json()
    assert [u["email"] for u in found["items"]] == ["joana@example.com"]
    admins = (await client.get("/api/v1/admin/users?role=admin", headers=admin_h)).json()
    assert [u["email"] for u in admins["items"]] == ["admin@example.com"]


async def test_conta_desativada_nao_entra_e_perde_a_sessao(client, db, admin_h):
    tokens = await register(client, email="bloq@example.com")
    h = auth(tokens["access_token"])
    user = await db.scalar(select(User).where(User.email == "bloq@example.com"))

    resp = await client.patch(
        f"/api/v1/admin/users/{user.id}", headers=admin_h, json={"disabled": True}
    )
    assert resp.status_code == 200
    assert resp.json()["disabled_at"] is not None

    me = await client.get("/api/v1/me", headers=h)
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "account_disabled"
    login = await client.post(
        "/api/v1/auth/login", json={"email": "bloq@example.com", "password": PASSWORD}
    )
    assert login.json()["error"]["code"] == "account_disabled"
    # o cookie de refresh do cadastro foi revogado
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    await client.patch(f"/api/v1/admin/users/{user.id}", headers=admin_h, json={"disabled": False})
    login = await client.post(
        "/api/v1/auth/login", json={"email": "bloq@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200


async def test_admin_promove_aluno_a_professor_mas_nao_mexe_em_admin(client, db, admin_h):
    await register(client, email="vira-prof@example.com")
    user = await db.scalar(select(User).where(User.email == "vira-prof@example.com"))
    resp = await client.patch(
        f"/api/v1/admin/users/{user.id}", headers=admin_h, json={"role": "teacher"}
    )
    assert resp.json()["role"] == "teacher"

    admin = await db.scalar(select(User).where(User.email == "admin@example.com"))
    resp = await client.patch(
        f"/api/v1/admin/users/{admin.id}", headers=admin_h, json={"disabled": True}
    )
    assert resp.status_code == 409
    resp = await client.patch(
        f"/api/v1/admin/users/{user.id}", headers=admin_h, json={"role": "admin"}
    )
    assert resp.status_code == 422


async def test_admin_exclui_conta_de_teste_mas_nao_admin(client, db, admin_h):
    tokens = await register(client, email="teste-apagar@example.com")
    h = auth(tokens["access_token"])
    user = await db.scalar(select(User).where(User.email == "teste-apagar@example.com"))
    user_id = user.id

    # aluno comum não pode excluir ninguém
    assert (await client.delete(f"/api/v1/admin/users/{user_id}", headers=h)).status_code == 403

    resp = await client.delete(f"/api/v1/admin/users/{user_id}", headers=admin_h)
    assert resp.status_code == 204
    db.expire_all()
    assert await db.get(User, user_id) is None
    assert (await client.get("/api/v1/me", headers=h)).status_code == 401
    # a senha antiga não entra mais
    login = await client.post(
        "/api/v1/auth/login", json={"email": "teste-apagar@example.com", "password": PASSWORD}
    )
    assert login.status_code == 401

    resp = await client.delete(f"/api/v1/admin/users/{user_id}", headers=admin_h)
    assert resp.status_code == 404

    admin = await db.scalar(select(User).where(User.email == "admin@example.com"))
    resp = await client.delete(f"/api/v1/admin/users/{admin.id}", headers=admin_h)
    assert resp.status_code == 409
