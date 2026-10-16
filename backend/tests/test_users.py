from sqlalchemy import select

from app.core.security import create_unsubscribe_token
from app.jobs.models import Job
from app.jobs.runner import process_next
from app.modules.users.models import User
from app.storage import get_storage
from tests.helpers import auth, register


async def test_get_e_patch_me(client):
    tokens = await register(client)
    h = auth(tokens["access_token"])
    me = (await client.get("/api/v1/me", headers=h)).json()
    assert me["timezone"] == "America/Sao_Paulo"
    assert me["email_verified"] is False
    assert "password_hash" not in me

    resp = await client.patch(
        "/api/v1/me",
        headers=h,
        json={
            "name": "  Maria S.  ",
            "timezone": "America/Recife",
            "target_exam_year": 2027,
            "email_reminders_enabled": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Maria S."
    assert body["timezone"] == "America/Recife"
    assert body["target_exam_year"] == 2027
    assert body["email_reminders_enabled"] is False


async def test_patch_me_valida_fuso(client):
    tokens = await register(client)
    resp = await client.patch(
        "/api/v1/me", headers=auth(tokens["access_token"]), json={"timezone": "Marte/Base"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["fields"][0]["field"] == "timezone"


async def test_excluir_conta_apaga_dados_e_arquivos(client, db, session_factory):
    tokens = await register(client)
    user = await db.scalar(select(User))
    storage = get_storage()
    await storage.put(f"users/{user.id}/essays/x/original.jpg", b"img", "image/jpeg")

    resp = await client.delete("/api/v1/me", headers=auth(tokens["access_token"]))
    assert resp.status_code == 204
    assert 'refresh_token=""' in resp.headers["set-cookie"]
    db.expire_all()
    assert await db.scalar(select(User)) is None

    job = await db.scalar(select(Job).where(Job.queue == "user.purge_storage"))
    assert job.payload == {"user_id": str(user.id)}
    # processa a fila: e-mail de verificação (console) + limpeza do storage
    while await process_next(session_factory):
        pass
    assert not storage.path_for(f"users/{user.id}").exists()


async def test_descadastro_de_lembretes(client, db):
    await register(client)
    user = await db.scalar(select(User))
    token = create_unsubscribe_token(user.id)

    resp = await client.get("/api/v1/me/unsubscribe", params={"token": token})
    assert resp.status_code == 200
    assert resp.json() == {"email_reminders_enabled": False}
    await db.refresh(user)
    assert user.email_reminders_enabled is False

    resp = await client.get("/api/v1/me/unsubscribe", params={"token": "invalido"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_token"
