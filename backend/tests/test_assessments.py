"""Provas do professor: montagem, link para os alunos, gabarito só na entrega e resultados."""

import json

import pytest
from sqlalchemy import select, update

from app.core.enums import UserRole
from app.modules.questions.models import KnowledgeArea, Question, QuestionOption
from app.modules.users.models import User
from tests.helpers import auth, register


@pytest.fixture
async def questions(db):
    """3 questões de MT com gabarito A, B e C, e 1 anulada."""
    mt = await db.scalar(select(KnowledgeArea.id).where(KnowledgeArea.code == "MT"))
    qs = [
        Question(
            year=2023,
            area_id=mt,
            statement_md=f"Enunciado {n}",
            correct_option=key,
            explanation_md=f"Resolução {key}",
        )
        for n, key in enumerate("ABC", start=1)
    ]
    annulled = Question(
        year=2022, area_id=mt, statement_md="Anulada", correct_option=None, is_annulled=True
    )
    db.add_all([*qs, annulled])
    await db.flush()
    for q in qs:
        db.add_all(
            QuestionOption(question_id=q.id, letter=x, text_md=f"Opção {x}") for x in "ABCDE"
        )
    await db.commit()
    return {"ids": [q.id for q in qs], "annulled": annulled.id}


async def _user(client, db, email, name, role=UserRole.student):
    tokens = await register(client, email=email, name=name)
    if role != UserRole.student:
        await db.execute(update(User).where(User.email == email).values(role=role))
        await db.commit()
    return auth(tokens["access_token"])


@pytest.fixture
async def teacher_h(client, db):
    return await _user(client, db, "prof@example.com", "Prof. Ana", UserRole.teacher)


async def _create(client, teacher_h, ids, **extra):
    resp = await client.post(
        "/api/v1/teacher/assessments",
        headers=teacher_h,
        json={"title": "Simulado de funções", "question_ids": ids, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _no_answer_key(payload) -> bool:
    text = json.dumps(payload)
    return "correct_option" not in text and "Resolução" not in text


async def test_aluno_nao_acessa_area_do_professor(client, db, questions):
    h = await _user(client, db, "aluno@example.com", "Aluno")
    resp = await client.post(
        "/api/v1/teacher/assessments",
        headers=h,
        json={"title": "x", "question_ids": questions["ids"]},
    )
    assert resp.status_code == 403
    assert (await client.get("/api/v1/teacher/assessments", headers=h)).status_code == 403


async def test_professor_monta_prova_com_gabarito_e_nao_aceita_anulada(
    client, teacher_h, questions
):
    ids = questions["ids"]
    resp = await client.post(
        "/api/v1/teacher/assessments",
        headers=teacher_h,
        json={"title": "x", "question_ids": [ids[0], questions["annulled"]]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["details"]["question_ids"] == [questions["annulled"]]

    a = await _create(client, teacher_h, [ids[2], ids[0]], instructions="Sem consulta.")
    assert a["is_open"] is False
    assert a["url"].endswith(f"/provas/{a['share_code']}")
    assert [(q["id"], q["position"], q["correct_option"]) for q in a["questions"]] == [
        (ids[2], 1, "C"),
        (ids[0], 2, "A"),
    ]
    listed = (await client.get("/api/v1/teacher/assessments", headers=teacher_h)).json()
    assert [(x["id"], x["question_count"]) for x in listed] == [(a["id"], 2)]


async def test_fluxo_do_aluno_e_resultados_do_professor(client, db, teacher_h, questions):
    ids = questions["ids"]
    a = await _create(client, teacher_h, ids)
    code = a["share_code"]
    joao = await _user(client, db, "joao@example.com", "João")
    bia = await _user(client, db, "bia@example.com", "Bia")

    info = (await client.get(f"/api/v1/assessments/by-code/{code}", headers=joao)).json()
    assert info["teacher_name"] == "Prof. Ana"
    assert info["question_count"] == 3
    assert info["attempt"] is None

    # fechada: ninguém começa
    resp = await client.post(f"/api/v1/assessments/by-code/{code}/start", headers=joao)
    assert resp.json()["error"]["code"] == "assessment_closed"

    await client.patch(
        f"/api/v1/teacher/assessments/{a['id']}", headers=teacher_h, json={"is_open": True}
    )
    started = (await client.post(f"/api/v1/assessments/by-code/{code}/start", headers=joao)).json()
    assert [q["id"] for q in started["questions"]] == ids
    assert started["result"] is None
    assert _no_answer_key(started)
    att = started["attempt"]["id"]

    async def answer(h, attempt, qid, letter):
        return await client.put(
            f"/api/v1/assessments/attempts/{attempt}/answers/{qid}",
            headers=h,
            json={"selected_option": letter},
        )

    assert (await answer(joao, att, ids[0], "A")).status_code == 204
    assert (await answer(joao, att, ids[1], "D")).status_code == 204
    assert (await answer(joao, att, ids[1], "B")).status_code == 204  # trocou de ideia
    assert (await answer(joao, att, questions["annulled"], "A")).status_code == 422

    # retomar devolve as respostas, ainda sem gabarito
    again = (await client.post(f"/api/v1/assessments/by-code/{code}/start", headers=joao)).json()
    assert again["attempt"]["id"] == att
    assert again["answers"] == {str(ids[0]): "A", str(ids[1]): "B"}
    assert _no_answer_key(again)

    # outro aluno não mexe na tentativa do João
    assert (await answer(bia, att, ids[0], "E")).status_code == 404

    done = (await client.post(f"/api/v1/assessments/attempts/{att}/finish", headers=joao)).json()
    assert (done["attempt"]["correct"], done["attempt"]["total"]) == (2, 3)
    assert [(r["selected_option"], r["is_correct"]) for r in done["result"]] == [
        ("A", True),
        ("B", True),
        (None, False),
    ]
    assert done["result"][0]["explanation_md"] == "Resolução A"
    assert (await answer(joao, att, ids[2], "C")).status_code == 409

    bia_att = (await client.post(f"/api/v1/assessments/by-code/{code}/start", headers=bia)).json()
    await answer(bia, bia_att["attempt"]["id"], ids[0], "E")

    res = (
        await client.get(f"/api/v1/teacher/assessments/{a['id']}/results", headers=teacher_h)
    ).json()
    rows = {r["student_name"]: r for r in res["attempts"]}
    assert rows["João"]["correct"] == 2
    assert rows["João"]["pct"] == 66.7
    assert rows["Bia"]["finished_at"] is None
    assert rows["Bia"]["correct"] is None
    assert rows["Bia"]["answered"] == 1
    assert res["finished"] == 1
    # acerto por questão só conta quem entregou
    assert [(q["answered"], q["correct"]) for q in res["questions"]] == [(1, 1), (1, 1), (0, 0)]

    # com alunos na prova, as questões não mudam mais
    resp = await client.patch(
        f"/api/v1/teacher/assessments/{a['id']}",
        headers=teacher_h,
        json={"question_ids": ids[:1]},
    )
    assert resp.json()["error"]["code"] == "assessment_has_attempts"

    # fechar a prova trava respostas de quem ainda não entregou
    await client.patch(
        f"/api/v1/teacher/assessments/{a['id']}", headers=teacher_h, json={"is_open": False}
    )
    resp = await answer(bia, bia_att["attempt"]["id"], ids[1], "B")
    assert resp.json()["error"]["code"] == "assessment_closed"


async def test_outro_professor_nao_ve_a_prova(client, db, teacher_h, questions):
    a = await _create(client, teacher_h, questions["ids"])
    other = await _user(client, db, "prof2@example.com", "Prof. Bruno", UserRole.teacher)
    for path in ("", "/results"):
        resp = await client.get(f"/api/v1/teacher/assessments/{a['id']}{path}", headers=other)
        assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/teacher/assessments/{a['id']}", headers=other)
    assert resp.status_code == 404
    resp = await client.delete(f"/api/v1/teacher/assessments/{a['id']}", headers=teacher_h)
    assert resp.status_code == 204
