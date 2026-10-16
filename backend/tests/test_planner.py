from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update

from app.email.models import EmailLog
from app.jobs.models import Job
from app.modules.planner.reminders import send_due_reminders
from app.modules.questions.models import KnowledgeArea, Subject
from app.modules.users.models import User
from tests.helpers import auth, register

API = "/api/v1/study-plans"


@pytest.fixture
async def token(client):
    return (await register(client))["access_token"]


async def _plan(client, h, name="Período de aulas"):
    r = await client.post(API, headers=h, json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _block(weekday=1, start="10:00", end="11:00", **kw):
    return {"weekday": weekday, "start_time": start, "end_time": end, "title": "Revisão", **kw}


async def test_primeiro_plano_nasce_ativo_e_ativacao_unica(client, token):
    h = auth(token)
    p1 = await _plan(client, h)
    assert p1["is_active"] is True
    p2 = await _plan(client, h, "Férias")
    assert p2["is_active"] is False
    r = await client.post(f"{API}/{p2['id']}/activate", headers=h)
    assert r.json()["is_active"] is True
    plans = (await client.get(API, headers=h)).json()
    assert [p["is_active"] for p in plans] == [True, False]
    assert plans[0]["id"] == p2["id"]
    assert (await client.get(f"{API}/active", headers=h)).json()["id"] == p2["id"]


async def test_sem_plano_ativo(client, token):
    r = await client.get(f"{API}/active", headers=auth(token))
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_active_plan"


async def test_sobreposicao_recusada_e_blocos_encostados_aceitos(client, token):
    h = auth(token)
    plan = await _plan(client, h)
    url = f"{API}/{plan['id']}/blocks"
    assert (await client.post(url, headers=h, json=_block())).status_code == 201
    # encostados: 10:00–11:00 e 11:00–12:00
    r = await client.post(url, headers=h, json=_block(start="11:00", end="12:00"))
    assert r.status_code == 201
    # sobreposto
    r = await client.post(url, headers=h, json=_block(start="10:30", end="11:30"))
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "block_overlap"
    assert err["details"]["conflict"]["start_time"] == "10:00:00"
    # outro dia, mesmo horário: ok
    assert (
        await client.post(url, headers=h, json=_block(weekday=2, start="10:30", end="11:30"))
    ).status_code == 201


async def test_mover_bloco_valida_sobreposicao_excluindo_ele_mesmo(client, token):
    h = auth(token)
    plan = await _plan(client, h)
    url = f"{API}/{plan['id']}/blocks"
    a = (await client.post(url, headers=h, json=_block())).json()
    await client.post(url, headers=h, json=_block(start="12:00", end="13:00"))
    # redimensionar o próprio bloco não conflita consigo mesmo
    r = await client.patch(f"{url}/{a['id']}", headers=h, json={"end_time": "11:30"})
    assert r.status_code == 200 and r.json()["end_time"] == "11:30:00"
    r = await client.patch(f"{url}/{a['id']}", headers=h, json={"end_time": "12:30"})
    assert r.status_code == 409
    r = await client.patch(f"{url}/{a['id']}", headers=h, json={"weekday": 3})
    assert r.status_code == 200 and r.json()["weekday"] == 3


async def test_validacoes_de_bloco(client, db, token):
    h = auth(token)
    plan = await _plan(client, h)
    url = f"{API}/{plan['id']}/blocks"

    async def code(payload):
        r = await client.post(url, headers=h, json=payload)
        return r.status_code, r.json()["error"]["code"]

    assert await code(_block(start="11:00", end="10:00")) == (422, "validation_error")
    assert await code(_block(start="10:07", end="11:00")) == (422, "validation_error")
    assert await code({"weekday": 1, "start_time": "10:00", "end_time": "11:00"}) == (
        422,
        "validation_error",
    )
    assert await code(_block(color="vermelho")) == (422, "validation_error")
    mat = await db.scalar(select(Subject).where(Subject.slug == "matematica"))
    lc = await db.scalar(select(KnowledgeArea).where(KnowledgeArea.code == "LC"))
    assert await code(_block(subject_id=mat.id, area_id=lc.id)) == (422, "subject_area_mismatch")
    r = await client.post(url, headers=h, json=_block(subject_id=mat.id, title=None))
    assert r.status_code == 201
    body = r.json()
    assert body["area_code"] == "MT" and body["color"] == "#7c3aed"  # cor padrão da área


async def test_duplicar_e_resumo(client, token):
    h = auth(token)
    plan = await _plan(client, h)
    url = f"{API}/{plan['id']}/blocks"
    await client.post(url, headers=h, json=_block(area_id=4, start="08:00", end="09:30"))
    await client.post(url, headers=h, json=_block(weekday=2, start="14:00", end="15:00"))
    s = (await client.get(f"{API}/{plan['id']}/summary", headers=h)).json()
    assert s["total_hours"] == 2.5
    assert {a["key"]: a["hours"] for a in s["by_area"]} == {"MT": 1.5, "OUTRO": 1.0}
    assert [d["hours"] for d in s["by_day"]] == [1.5, 1.0, 0, 0, 0, 0, 0]

    copy = (await client.post(f"{API}/{plan['id']}/duplicate", headers=h)).json()
    assert copy["name"].endswith("(cópia)") and copy["is_active"] is False
    assert len(copy["blocks"]) == 2


async def test_plano_de_outro_usuario(client, token):
    plan = await _plan(client, auth(token))
    other = (await register(client, email="outro@example.com"))["access_token"]
    assert (await client.get(f"{API}/{plan['id']}", headers=auth(other))).status_code == 404


# ---- lembretes ----------------------------------------------------------------


async def _user_with_block(client, db, email, tz):
    tokens = await register(client, email=email)
    await db.execute(
        update(User)
        .where(User.email == email)
        .values(timezone=tz, email_verified_at=datetime.now(UTC))
    )
    await db.commit()
    h = auth(tokens["access_token"])
    plan = await _plan(client, h)
    # segunda-feira 19:00, lembrete 15 min antes
    r = await client.post(
        f"{API}/{plan['id']}/blocks",
        headers=h,
        json=_block(
            weekday=1, start="19:00", end="20:30", reminder_minutes_before=15, title="Matemática"
        ),
    )
    assert r.status_code == 201
    return r.json()


async def _reminders(db):
    db.expire_all()
    return [
        (log.to_email, log.dedupe_key)
        for log in await db.scalars(select(EmailLog).where(EmailLog.type == "study_reminder"))
    ]


async def test_lembrete_unico_no_horario_certo_por_fuso(client, db):
    recife = await _user_with_block(client, db, "recife@example.com", "America/Recife")
    manaus = await _user_with_block(client, db, "manaus@example.com", "America/Manaus")
    # 2026-10-19 é segunda. 18:45 em Recife (UTC−3) = 21:45 UTC; em Manaus (UTC−4) = 22:45 UTC.
    assert await send_due_reminders(db, datetime(2026, 10, 19, 21, 44, tzinfo=UTC)) == 0
    assert await send_due_reminders(db, datetime(2026, 10, 19, 21, 45, tzinfo=UTC)) == 1
    assert await _reminders(db) == [("recife@example.com", f"reminder:{recife['id']}:2026-10-19")]
    # ticks seguintes dentro da janela não duplicam
    assert await send_due_reminders(db, datetime(2026, 10, 19, 21, 46, tzinfo=UTC)) == 0
    assert await send_due_reminders(db, datetime(2026, 10, 19, 21, 50, tzinfo=UTC)) == 0
    assert await send_due_reminders(db, datetime(2026, 10, 19, 22, 45, tzinfo=UTC)) == 1
    logs = await _reminders(db)
    assert len(logs) == 2
    assert ("manaus@example.com", f"reminder:{manaus['id']}:2026-10-19") in logs
    # o e-mail tem o link de descadastro
    job = await db.scalar(
        select(Job).where(
            Job.queue == "email.send",
            Job.payload["to"].astext == "manaus@example.com",
            Job.payload["subject"].astext.startswith("Lembrete"),
        )
    )
    assert "/descadastrar?token=" in job.payload["html"]
    # semana seguinte: nova ocorrência, novo lembrete
    assert await send_due_reminders(db, datetime(2026, 10, 26, 21, 45, tzinfo=UTC)) == 1


async def test_lembrete_respeita_descadastro_e_plano_inativo(client, db):
    await _user_with_block(client, db, "recife@example.com", "America/Recife")
    await db.execute(update(User).values(email_reminders_enabled=False))
    await db.commit()
    assert await send_due_reminders(db, datetime(2026, 10, 19, 21, 45, tzinfo=UTC)) == 0


async def test_lembrete_na_vespera_cruza_o_dia(client, db):
    """Bloco segunda 00:30 com lembrete 60 min antes dispara domingo 23:30 local."""
    tokens = await register(client, email="sp@example.com")
    await db.execute(update(User).values(email_verified_at=datetime.now(UTC)))
    await db.commit()
    h = auth(tokens["access_token"])
    plan = await _plan(client, h)
    await client.post(
        f"{API}/{plan['id']}/blocks",
        headers=h,
        json=_block(weekday=1, start="00:30", end="01:30", reminder_minutes_before=60),
    )
    # domingo 2026-10-18 23:30 em São Paulo (UTC−3) = segunda 02:30 UTC
    assert await send_due_reminders(db, datetime(2026, 10, 19, 2, 30, tzinfo=UTC)) == 1
    [(_, key)] = await _reminders(db)
    assert key.endswith(":2026-10-19")  # data da ocorrência (segunda), não do disparo
