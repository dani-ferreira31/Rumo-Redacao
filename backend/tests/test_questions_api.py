import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, update

from app.core.enums import UserRole
from app.modules.questions.models import (
    KnowledgeArea,
    Question,
    QuestionAttempt,
    QuestionOption,
    Subject,
    Topic,
)
from app.modules.users.models import User
from tests.helpers import auth, register


@pytest.fixture
async def bank(db):
    """6 questões: 3 de MT, 2 de LC (1 de inglês), 1 anulada."""
    areas = {a.code: a.id for a in await db.scalars(select(KnowledgeArea))}
    mat = await db.scalar(select(Subject).where(Subject.slug == "matematica"))
    topic = Topic(subject_id=mat.id, name="Funções", slug="funcoes-teste")
    db.add(topic)
    specs = [
        ("MT", "Uma função quadrática descreve a trajetória.", "A", Decimal_("0.2"), None),
        ("MT", "Calcule a porcentagem de aumento do preço.", "B", Decimal_("1.0"), None),
        ("MT", "Probabilidade de sortear duas bolas azuis.", "C", Decimal_("2.3"), None),
        ("LC", "Leia o poema e identifique a função da linguagem.", "D", None, None),
        ("LC", "Read the cartoon about climate change.", "E", None, "ingles"),
    ]
    qs = []
    for area, text, answer, b, lang in specs:
        q = Question(
            year=2023,
            area_id=areas[area],
            statement_md=text,
            correct_option=answer,
            irt_b=b,
            foreign_language=lang,
            explanation_md=f"Resolução {answer}",
            subject_id=mat.id if area == "MT" else None,
        )
        db.add(q)
        qs.append(q)
    annulled = Question(
        year=2022,
        area_id=areas["CH"],
        statement_md="Questão anulada",
        correct_option=None,
        is_annulled=True,
    )
    db.add(annulled)
    await db.flush()
    for q in qs:
        for letter in "ABCDE":
            db.add(QuestionOption(question_id=q.id, letter=letter, text_md=f"Opção {letter}"))
    from app.modules.questions.models import QuestionTopic

    db.add(QuestionTopic(question_id=qs[0].id, topic_id=topic.id))
    await db.commit()
    return {"qs": qs, "annulled": annulled, "topic": topic, "mat": mat}


def Decimal_(v):  # noqa: N802
    from decimal import Decimal

    return Decimal(v)


@pytest.fixture
async def token(client):
    return (await register(client))["access_token"]


def _no_answer_key(payload) -> bool:
    text = json.dumps(payload)
    return "correct_option" not in text and "explanation" not in text


async def test_gabarito_nunca_aparece_antes_da_resposta(client, token, bank):
    h = auth(token)
    resp = await client.get("/api/v1/questions", headers=h)
    assert resp.status_code == 200
    assert _no_answer_key(resp.json())
    q = bank["qs"][0]
    detail = (await client.get(f"/api/v1/questions/{q.id}", headers=h)).json()
    assert _no_answer_key(detail)
    assert [o["letter"] for o in detail["options"]] == list("ABCDE")

    resp = await client.post(
        f"/api/v1/questions/{q.id}/answer",
        headers=h,
        json={"selected_option": "B", "time_spent_seconds": 40},
    )
    body = resp.json()
    assert body == {
        "recorded": True,
        "is_correct": False,
        "correct_option": "A",
        "explanation_md": "Resolução A",
    }


async def test_filtros(client, token, bank):
    h = auth(token)

    async def ids(**params):
        r = await client.get("/api/v1/questions", headers=h, params=params)
        assert r.status_code == 200, r.text
        return {i["id"] for i in r.json()["items"]}

    qs = bank["qs"]
    assert bank["annulled"].id not in await ids()
    assert await ids(area="MT") == {q.id for q in qs[:3]}
    assert await ids(difficulty="facil") == {qs[0].id}
    assert await ids(difficulty="media") == {qs[1].id}
    assert await ids(difficulty="dificil") == {qs[2].id}
    assert await ids(topic_id=bank["topic"].id) == {qs[0].id}
    assert await ids(subject_id=bank["mat"].id) == {q.id for q in qs[:3]}
    # inglês inclui as questões sem idioma e exclui espanhol
    assert qs[4].id in await ids(language="ingles")
    assert qs[4].id not in await ids(language="espanhol")
    # busca sem acentos e com plural regular
    assert await ids(q="funcao quadratica") == {qs[0].id}
    assert await ids(q="aumentos precos") == {qs[1].id}  # plural regular, sem acento


async def test_status_respondidas_erradas_favoritas(client, token, bank):
    h = auth(token)
    q0, q1 = bank["qs"][0], bank["qs"][1]
    await client.post(f"/api/v1/questions/{q0.id}/answer", headers=h, json={"selected_option": "A"})
    await client.post(f"/api/v1/questions/{q1.id}/answer", headers=h, json={"selected_option": "A"})
    assert (await client.put(f"/api/v1/questions/{q1.id}/bookmark", headers=h)).status_code == 204
    await client.put(f"/api/v1/questions/{q1.id}/bookmark", headers=h)  # idempotente

    async def ids(status):
        r = await client.get("/api/v1/questions", headers=h, params={"status": status})
        return {i["id"] for i in r.json()["items"]}

    assert q0.id not in await ids("nao_respondidas")
    assert await ids("erradas") == {q1.id}
    assert await ids("favoritas") == {q1.id}
    # acertar depois tira da lista de erradas (vale a última tentativa)
    await client.post(f"/api/v1/questions/{q1.id}/answer", headers=h, json={"selected_option": "B"})
    assert await ids("erradas") == set()
    assert (
        await client.delete(f"/api/v1/questions/{q1.id}/bookmark", headers=h)
    ).status_code == 204
    assert await ids("favoritas") == set()


async def test_lista_so_mostra_gabarito_ao_encerrar(client, token, bank):
    h = auth(token)
    resp = await client.post(
        "/api/v1/practice-sessions",
        headers=h,
        json={"mode": "lista", "filters": {"area": "MT"}, "size": 3},
    )
    assert resp.status_code == 201, resp.text
    sess = resp.json()
    assert sorted(sess["question_ids"]) == sorted(q.id for q in bank["qs"][:3])
    answers = {bank["qs"][0].id: "A", bank["qs"][1].id: "C"}
    for qid, opt in answers.items():
        r = await client.post(
            f"/api/v1/questions/{qid}/answer",
            headers=h,
            json={"selected_option": opt, "practice_session_id": sess["id"]},
        )
        assert r.json() == {
            "recorded": True,
            "is_correct": None,
            "correct_option": None,
            "explanation_md": None,
        }
    progress = (await client.get(f"/api/v1/practice-sessions/{sess['id']}", headers=h)).json()
    assert {int(k): v for k, v in progress["answers"].items()} == answers
    assert _no_answer_key(progress)

    result = (await client.post(f"/api/v1/practice-sessions/{sess['id']}/finish", headers=h)).json()
    assert result["total"] == 3 and result["answered"] == 2 and result["correct"] == 1
    assert result["by_area"] == [
        {
            "code": "MT",
            "name": result["by_area"][0]["name"],
            "answered": 2,
            "correct": 1,
            "pct": 50.0,
        }
    ]
    r = await client.post(
        f"/api/v1/questions/{bank['qs'][2].id}/answer",
        headers=h,
        json={"selected_option": "C", "practice_session_id": sess["id"]},
    )
    assert r.status_code == 409


async def test_sessao_de_outro_usuario_e_questao_fora_da_sessao(client, token, bank):
    h = auth(token)
    sess = (
        await client.post(
            "/api/v1/practice-sessions",
            headers=h,
            json={"mode": "livre", "filters": {"area": "MT"}, "size": 1},
        )
    ).json()
    outside = next(q for q in bank["qs"] if q.id not in sess["question_ids"])
    r = await client.post(
        f"/api/v1/questions/{outside.id}/answer",
        headers=h,
        json={"selected_option": "A", "practice_session_id": sess["id"]},
    )
    assert r.status_code == 422
    other = (await register(client, email="outro@example.com"))["access_token"]
    r = await client.get(f"/api/v1/practice-sessions/{sess['id']}", headers=auth(other))
    assert r.status_code == 404


async def test_estatisticas_batem_com_as_tentativas(client, db, token, bank):
    h = auth(token)
    q = bank["qs"]
    for qid, opt in [(q[0].id, "B"), (q[0].id, "A"), (q[1].id, "B"), (q[3].id, "A")]:
        await client.post(
            f"/api/v1/questions/{qid}/answer", headers=h, json={"selected_option": opt}
        )
    stats = (await client.get("/api/v1/questions/stats", headers=h)).json()
    assert (stats["answered"], stats["correct"]) == (3, 2)  # última tentativa por questão
    mt = next(a for a in stats["by_area"] if a["code"] == "MT")
    assert (mt["answered"], mt["correct"], mt["pct"]) == (2, 2, 100.0)
    lc = next(a for a in stats["by_area"] if a["code"] == "LC")
    assert (lc["answered"], lc["correct"]) == (1, 0)
    assert stats["by_topic"][0]["name"] == "Funções"
    assert sum(p["answered"] for p in stats["timeline"]) == 4  # a série conta todas
    count = len((await db.scalars(select(QuestionAttempt))).all())
    assert count == 4


async def test_questao_anulada_nao_aparece(client, token, bank):
    r = await client.get(f"/api/v1/questions/{bank['annulled'].id}", headers=auth(token))
    assert r.status_code == 404


async def test_admin_revisa_questao(client, db, token, bank):
    h = auth(token)
    q = bank["qs"][3]
    assert (await client.get("/api/v1/admin/questions", headers=h)).status_code == 403
    await db.execute(update(User).values(role=UserRole.admin, email_verified_at=datetime.now(UTC)))
    await db.commit()
    queue = (
        await client.get("/api/v1/admin/questions", headers=h, params={"reviewed": "false"})
    ).json()
    assert queue["total"] == 6
    detail = (await client.get(f"/api/v1/admin/questions/{q.id}", headers=h)).json()
    assert detail["correct_option"] == "D"
    portugues = await db.scalar(select(Subject).where(Subject.slug == "portugues"))
    r = await client.patch(
        f"/api/v1/admin/questions/{q.id}",
        headers=h,
        json={"subject_id": portugues.id, "reviewed": True, "explanation_md": "Função poética."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["subject"]["id"] == portugues.id and r.json()["reviewed"] is True
    mat = bank["mat"]
    r = await client.patch(
        f"/api/v1/admin/questions/{q.id}", headers=h, json={"subject_id": mat.id}
    )
    assert r.json()["error"]["code"] == "invalid_subject"
    queue = (
        await client.get("/api/v1/admin/questions", headers=h, params={"reviewed": "false"})
    ).json()
    assert queue["total"] == 5


async def test_catalogo(client, token, bank):
    tree = (await client.get("/api/v1/catalog/areas", headers=auth(token))).json()
    assert [a["code"] for a in tree] == ["LC", "CH", "CN", "MT", "CP"]
    mt = tree[3]
    assert any(t["name"] == "Funções" for t in mt["subjects"][0]["topics"])
