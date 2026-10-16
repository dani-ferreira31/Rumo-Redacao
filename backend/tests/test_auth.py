from datetime import timedelta

import time_machine
from sqlalchemy import select

from app.core.security import hash_token, utcnow
from app.modules.auth.models import RefreshToken
from app.modules.users.models import User
from tests.helpers import (
    PASSWORD,
    auth,
    email_jobs,
    last_email_token,
    minor_birth_date,
    register,
    register_payload,
)

API = "/api/v1/auth"


def _refresh_cookie(resp) -> str:
    return resp.cookies["refresh_token"]


async def _refresh(client, cookie: str):
    client.cookies.clear()
    client.cookies.set("refresh_token", cookie)
    return await client.post(f"{API}/refresh")


# ---- cadastro ---------------------------------------------------------------


async def test_cadastro_cria_usuario_inicia_sessao_e_envia_verificacao(client, db):
    resp = await client.post(f"{API}/register", json=register_payload(email="Maria@Example.com"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    cookie = resp.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie and "SameSite=lax" in cookie

    user = await db.scalar(select(User).where(User.email == "maria@example.com"))
    assert user.email_verified_at is None
    assert user.guardian_consent_at is None
    assert user.password_hash != PASSWORD

    jobs = await email_jobs(db, "maria@example.com")
    assert len(jobs) == 1
    assert "/verificar-email?token=" in jobs[0].payload["html"]


async def test_cadastro_email_duplicado_ignora_maiusculas(client):
    await register(client)
    resp = await client.post(f"{API}/register", json=register_payload(email="MARIA@example.com"))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_already_registered"


async def test_menor_sem_consentimento_e_rejeitado(client):
    resp = await client.post(
        f"{API}/register", json=register_payload(birth_date=minor_birth_date())
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "guardian_consent_required"


async def test_menor_com_consentimento_registra_data(client, db):
    await register(client, birth_date=minor_birth_date(), guardian_consent=True)
    user = await db.scalar(select(User).where(User.email == "maria@example.com"))
    assert user.guardian_consent_at is not None


async def test_senha_fraca_e_dados_invalidos(client):
    resp = await client.post(f"{API}/register", json=register_payload(password="curta"))
    assert resp.status_code == 422
    fields = {f["field"] for f in resp.json()["error"]["details"]["fields"]}
    assert fields == {"password"}

    resp = await client.post(
        f"{API}/register", json=register_payload(email="nao-e-email", birth_date="2999-01-01")
    )
    fields = {f["field"] for f in resp.json()["error"]["details"]["fields"]}
    assert fields == {"email", "birth_date"}


# ---- login ------------------------------------------------------------------


async def test_login_ok(client):
    await register(client)
    resp = await client.post(
        f"{API}/login", json={"email": "MARIA@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 200
    me = await client.get("/api/v1/me", headers=auth(resp.json()["access_token"]))
    assert me.json()["email"] == "maria@example.com"


async def test_login_senha_errada_e_email_inexistente(client):
    await register(client)
    for payload in (
        {"email": "maria@example.com", "password": "errada-123"},
        {"email": "ninguem@example.com", "password": PASSWORD},
    ):
        resp = await client.post(f"{API}/login", json=payload)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_access_token_invalido_ou_expirado(client):
    tokens = await register(client)
    assert (await client.get("/api/v1/me")).json()["error"]["code"] == "not_authenticated"
    resp = await client.get("/api/v1/me", headers=auth("lixo"))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_access_token"
    with time_machine.travel(utcnow() + timedelta(minutes=16), tick=False):
        resp = await client.get("/api/v1/me", headers=auth(tokens["access_token"]))
    assert resp.status_code == 401


async def test_rate_limit_no_login(client):
    for _ in range(10):
        await client.post(f"{API}/login", json={"email": "x@example.com", "password": "abc"})
    resp = await client.post(f"{API}/login", json={"email": "x@example.com", "password": "abc"})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "rate_limited"


# ---- refresh / logout -------------------------------------------------------


async def test_refresh_rotaciona_o_token(client, db):
    resp = await client.post(f"{API}/register", json=register_payload())
    first = _refresh_cookie(resp)

    resp = await _refresh(client, first)
    assert resp.status_code == 200
    second = _refresh_cookie(resp)
    assert second != first
    assert resp.json()["access_token"]

    old = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(first)))
    await db.refresh(old)
    assert old.revoked_at is not None and old.replaced_by is not None


async def test_reuso_de_token_rotacionado_revoga_todas_as_sessoes(client, db):
    resp = await client.post(f"{API}/register", json=register_payload())
    first = _refresh_cookie(resp)
    second = _refresh_cookie(await _refresh(client, first))

    # dentro da janela de tolerância (duas abas), o reuso ainda é aceito
    assert (await _refresh(client, first)).status_code == 200

    with time_machine.travel(utcnow() + timedelta(minutes=1), tick=False):
        resp = await _refresh(client, first)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "refresh_token_reused"
        # o token legítimo mais novo também caiu
        assert (await _refresh(client, second)).status_code == 401


async def test_refresh_expirado_e_ausente(client):
    resp = await client.post(f"{API}/register", json=register_payload())
    cookie = _refresh_cookie(resp)
    with time_machine.travel(utcnow() + timedelta(days=31), tick=False):
        resp = await _refresh(client, cookie)
    assert resp.json()["error"]["code"] == "refresh_token_expired"

    client.cookies.clear()
    resp = await client.post(f"{API}/refresh")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "refresh_token_missing"


async def test_logout_revoga_o_refresh(client):
    resp = await client.post(f"{API}/register", json=register_payload())
    cookie = _refresh_cookie(resp)
    client.cookies.clear()
    client.cookies.set("refresh_token", cookie)
    resp = await client.post(f"{API}/logout")
    assert resp.status_code == 204
    assert 'refresh_token=""' in resp.headers["set-cookie"]
    assert (await _refresh(client, cookie)).status_code == 401


# ---- verificação de e-mail --------------------------------------------------


async def test_verifica_email(client, db):
    tokens = await register(client)
    token = await last_email_token(db, "/verificar-email")
    resp = await client.post(f"{API}/verify-email", json={"token": token})
    assert resp.status_code == 204
    me = await client.get("/api/v1/me", headers=auth(tokens["access_token"]))
    assert me.json()["email_verified"] is True

    resp = await client.post(f"{API}/verify-email", json={"token": token})
    assert resp.json()["error"]["code"] == "token_already_used"


async def test_token_de_verificacao_expirado(client, db):
    await register(client)
    token = await last_email_token(db, "/verificar-email")
    with time_machine.travel(utcnow() + timedelta(hours=25), tick=False):
        resp = await client.post(f"{API}/verify-email", json={"token": token})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "token_expired"


async def test_token_de_proposito_errado_e_invalido(client, db):
    await register(client)
    await client.post(f"{API}/forgot-password", json={"email": "maria@example.com"})
    reset_token = await last_email_token(db, "/redefinir-senha")
    resp = await client.post(f"{API}/verify-email", json={"token": reset_token})
    assert resp.json()["error"]["code"] == "invalid_token"
    resp = await client.post(f"{API}/verify-email", json={"token": "nao-existe"})
    assert resp.json()["error"]["code"] == "invalid_token"


async def test_reenviar_verificacao_invalida_o_link_anterior(client, db):
    tokens = await register(client)
    old = await last_email_token(db, "/verificar-email")
    resp = await client.post(f"{API}/resend-verification", headers=auth(tokens["access_token"]))
    assert resp.status_code == 204
    new = await last_email_token(db, "/verificar-email")
    assert new != old
    assert (await client.post(f"{API}/verify-email", json={"token": old})).status_code == 400
    assert (await client.post(f"{API}/verify-email", json={"token": new})).status_code == 204

    resp = await client.post(f"{API}/resend-verification", headers=auth(tokens["access_token"]))
    assert resp.json()["error"]["code"] == "email_already_verified"


# ---- esqueci / redefinir senha ----------------------------------------------


async def test_esqueci_senha_nao_revela_se_email_existe(client, db):
    await register(client)
    before = len(await email_jobs(db))
    resp = await client.post(f"{API}/forgot-password", json={"email": "ninguem@example.com"})
    assert resp.status_code == 204
    assert len(await email_jobs(db)) == before

    resp = await client.post(f"{API}/forgot-password", json={"email": "maria@example.com"})
    assert resp.status_code == 204
    assert len(await email_jobs(db)) == before + 1


async def test_redefinir_senha_troca_senha_e_derruba_sessoes(client, db):
    resp = await client.post(f"{API}/register", json=register_payload())
    cookie = _refresh_cookie(resp)
    await client.post(f"{API}/forgot-password", json={"email": "maria@example.com"})
    token = await last_email_token(db, "/redefinir-senha")

    resp = await client.post(
        f"{API}/reset-password", json={"token": token, "new_password": "nova-senha-456"}
    )
    assert resp.status_code == 204
    assert (await _refresh(client, cookie)).status_code == 401
    old_login = {"email": "maria@example.com", "password": PASSWORD}
    assert (await client.post(f"{API}/login", json=old_login)).status_code == 401
    new_login = {"email": "maria@example.com", "password": "nova-senha-456"}
    assert (await client.post(f"{API}/login", json=new_login)).status_code == 200

    user = await db.scalar(select(User))
    await db.refresh(user)
    assert user.email_verified_at is not None

    resp = await client.post(
        f"{API}/reset-password", json={"token": token, "new_password": "outra-senha-789"}
    )
    assert resp.json()["error"]["code"] == "token_already_used"


async def test_token_de_reset_expira_em_1_hora(client, db):
    await register(client)
    await client.post(f"{API}/forgot-password", json={"email": "maria@example.com"})
    token = await last_email_token(db, "/redefinir-senha")
    with time_machine.travel(utcnow() + timedelta(minutes=61), tick=False):
        resp = await client.post(
            f"{API}/reset-password", json={"token": token, "new_password": "nova-senha-456"}
        )
    assert resp.json()["error"]["code"] == "token_expired"
