"""Concursos: importação de PDF com IA simulada, revisão, figura, publicação e aluno."""

import io
from datetime import UTC, datetime

import pypdfium2 as pdfium
import pytest
from sqlalchemy import select, update

from app.ai.models import AIUsage
from app.core.enums import AIPurpose, ContestExamStatus, QuestionFormat, UserRole
from app.jobs.registry import load_handlers
from app.jobs.runner import process_next
from app.modules.contests.models import ContestExam, ContestExamQuestion
from app.modules.questions.models import Question, QuestionAsset
from app.modules.users.models import User
from app.storage import get_storage
from app.storage.base import ObjectNotFoundError
from tests.helpers import auth, register

load_handlers()


def make_pdf(pages: int) -> bytes:
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(595, 842)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


META = {
    "board": "Cebraspe",
    "organization": "Polícia Federal",
    "position": "Agente",
    "year": "2021",
    "level": "superior",
}


@pytest.fixture
async def admin_h(client, db):
    tokens = await register(client, email="admin@example.com", name="Admin")
    await db.execute(
        update(User)
        .where(User.email == "admin@example.com")
        .values(role=UserRole.admin, email_verified_at=datetime.now(UTC))
    )
    await db.commit()
    return auth(tokens["access_token"])


@pytest.fixture
async def student_h(client, db):
    tokens = await register(client, email="aluno@example.com", name="Aluno")
    return auth(tokens["access_token"])


async def _drain(session_factory):
    while await process_next(session_factory):
        pass


async def _import(client, admin_h, session_factory, pages=9, answer_key=True) -> int:
    files = {"exam_pdf": ("prova.pdf", make_pdf(pages), "application/pdf")}
    if answer_key:
        files["answer_key_pdf"] = ("gabarito.pdf", make_pdf(1), "application/pdf")
    resp = await client.post("/api/v1/admin/contests", headers=admin_h, data=META, files=files)
    assert resp.status_code == 202, resp.text
    exam_id = resp.json()["id"]
    await _drain(session_factory)
    return exam_id


async def test_estimativa_conta_paginas_e_trechos(client, admin_h):
    files = {"exam_pdf": ("prova.pdf", make_pdf(17), "application/pdf")}
    body = (
        await client.post("/api/v1/admin/contests/estimate", headers=admin_h, files=files)
    ).json()
    assert body["pages"] == 17 and body["chunks"] == 3
    assert body["provider"] == "fake" and body["estimated_cost_usd"] == 0


async def test_pdf_invalido(client, admin_h):
    files = {"exam_pdf": ("prova.pdf", b"nao sou pdf", "application/pdf")}
    resp = await client.post("/api/v1/admin/contests", headers=admin_h, data=META, files=files)
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "invalid_pdf"


async def test_importacao_revisao_e_publicacao(client, db, session_factory, admin_h, student_h):
    exam_id = await _import(client, admin_h, session_factory)
    detail = (await client.get(f"/api/v1/admin/contests/{exam_id}", headers=admin_h)).json()
    assert detail["status"] == "review" and detail["page_count"] == 9
    assert len(detail["page_urls"]) == 9
    qs = {q["position"]: q for q in detail["questions_list"]}
    # 2 questões por página; o trecho 1 (págs. 1–8 + extra) e o 2 (pág. 9) não se repetem
    assert sorted(qs) == list(range(1, 19))
    assert qs[3]["format"] == "true_false" and qs[3]["options"] == 0
    assert qs[3]["correct_option"] in ("C", "E")
    assert qs[1]["format"] == "multiple_choice" and qs[1]["options"] == 5
    assert qs[4]["is_annulled"] is True
    assert any("figura" in w for w in qs[5]["warnings"])
    assert qs[1]["subject_name"] is not None  # disciplina sugerida casou com a lista

    usage = (await db.scalars(select(AIUsage).where(AIUsage.contest_exam_id == exam_id))).all()
    assert len(usage) == 3  # 2 trechos + gabarito
    assert {u.purpose for u in usage} == {AIPurpose.contest_extraction}

    # antes de publicar, o aluno não vê nada
    page = await client.get("/api/v1/questions", headers=student_h, params={"track": "concurso"})
    assert page.json()["total"] == 0
    q1 = qs[1]["id"]
    assert (await client.get(f"/api/v1/questions/{q1}", headers=student_h)).status_code == 404

    assert (
        await client.post(f"/api/v1/admin/contests/{exam_id}/publish", headers=admin_h)
    ).status_code == 204
    page = (
        await client.get(
            "/api/v1/questions",
            headers=student_h,
            params={"track": "concurso", "board": "cebraspe"},
        )
    ).json()
    assert page["total"] == 17  # a anulada fica de fora
    assert page["items"][0]["track"] == "concurso"
    assert page["items"][0]["contest"] == "Cebraspe · Polícia Federal · Agente"
    # ENEM não mistura
    enem = (await client.get("/api/v1/questions", headers=student_h)).json()
    assert all(i["track"] == "enem" for i in enem["items"])

    tf = qs[3]["id"]
    detail_q = (await client.get(f"/api/v1/questions/{tf}", headers=student_h)).json()
    assert detail_q["format"] == "true_false" and "correct_option" not in detail_q
    assert detail_q["positions"][0]["label"].startswith("Cebraspe · Polícia Federal")
    resp = await client.post(
        f"/api/v1/questions/{tf}/answer", headers=student_h, json={"selected_option": "A"}
    )
    assert resp.status_code == 422
    resp = await client.post(
        f"/api/v1/questions/{tf}/answer",
        headers=student_h,
        json={"selected_option": qs[3]["correct_option"]},
    )
    assert resp.json()["is_correct"] is True

    filters = (await client.get("/api/v1/contests/filters", headers=student_h)).json()
    assert filters["boards"] == ["Cebraspe"] and filters["years"] == [2021]

    only_tf = (
        await client.get(
            "/api/v1/questions",
            headers=student_h,
            params={"track": "concurso", "format": "true_false"},
        )
    ).json()
    assert only_tf["total"] == 6


async def test_sem_gabarito_nao_publica_ate_informar_respostas(
    client, db, session_factory, admin_h
):
    exam_id = await _import(client, admin_h, session_factory, pages=1, answer_key=False)
    detail = (await client.get(f"/api/v1/admin/contests/{exam_id}", headers=admin_h)).json()
    assert detail["warnings"] == 2
    resp = await client.post(f"/api/v1/admin/contests/{exam_id}/publish", headers=admin_h)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "missing_answers"
    for q in detail["questions_list"]:
        resp = await client.patch(
            f"/api/v1/admin/questions/{q['id']}", headers=admin_h, json={"correct_option": "B"}
        )
        assert resp.status_code == 200, resp.text
    detail = (await client.get(f"/api/v1/admin/contests/{exam_id}", headers=admin_h)).json()
    assert detail["warnings"] == 0  # avisos de gabarito resolvidos pela edição
    assert (
        await client.post(f"/api/v1/admin/contests/{exam_id}/publish", headers=admin_h)
    ).status_code == 204


async def test_recorte_de_figura(client, db, session_factory, admin_h):
    exam_id = await _import(client, admin_h, session_factory, pages=3)
    detail = (await client.get(f"/api/v1/admin/contests/{exam_id}", headers=admin_h)).json()
    q5 = next(q for q in detail["questions_list"] if q["position"] == 5)
    resp = await client.post(
        f"/api/v1/admin/contests/{exam_id}/questions/{q5['id']}/figure",
        headers=admin_h,
        json={"page": 3, "x": 0.1, "y": 0.2, "width": 0.5, "height": 0.3, "alt": "Gráfico"},
    )
    assert resp.status_code == 204, resp.text
    q = await db.get(Question, q5["id"], populate_existing=True)
    assert "[Figura:" not in q.statement_md and "](asset:questions/concursos/" in q.statement_md
    [asset] = (
        await db.scalars(select(QuestionAsset).where(QuestionAsset.question_id == q.id))
    ).all()
    assert await get_storage().get(asset.storage_key)
    detail = (await client.get(f"/api/v1/admin/contests/{exam_id}", headers=admin_h)).json()
    q5 = next(q for q in detail["questions_list"] if q["position"] == 5)
    assert q5["assets"] == 1 and not any("figura" in w for w in q5["warnings"])


async def test_modulo_concursos_desligado(client, session_factory, admin_h, student_h):
    exam_id = await _import(client, admin_h, session_factory, pages=1)
    await client.post(f"/api/v1/admin/contests/{exam_id}/publish", headers=admin_h)
    await client.put(
        "/api/v1/admin/settings/features",
        headers=admin_h,
        json={"features": {"questions_concursos": False}},
    )
    resp = await client.get("/api/v1/questions", headers=student_h, params={"track": "concurso"})
    assert resp.status_code == 503
    assert (await client.get("/api/v1/questions", headers=student_h)).status_code == 200
    assert (await client.get("/api/v1/contests/filters", headers=student_h)).status_code == 503


async def test_excluir_prova_apaga_questoes_e_arquivos(client, db, session_factory, admin_h):
    exam_id = await _import(client, admin_h, session_factory, pages=1)
    ids = list(
        await db.scalars(
            select(ContestExamQuestion.question_id).where(
                ContestExamQuestion.contest_exam_id == exam_id
            )
        )
    )
    assert (
        await client.delete(f"/api/v1/admin/contests/{exam_id}", headers=admin_h)
    ).status_code == 204
    db.expire_all()
    assert await db.get(ContestExam, exam_id) is None
    assert (await db.scalars(select(Question).where(Question.id.in_(ids)))).all() == []
    with pytest.raises(ObjectNotFoundError):
        await get_storage().get(f"contests/{exam_id}/prova.pdf")


async def test_falha_da_ia_marca_prova_como_falha(
    client, db, session_factory, admin_h, monkeypatch
):
    from app.ai.types import AIRefusalError
    from app.modules.contests import extraction

    async def boom(*args, **kwargs):
        raise AIRefusalError("teste")

    monkeypatch.setattr(extraction, "extract_questions", boom)
    exam_id = await _import(client, admin_h, session_factory, pages=1)
    exam = await db.get(ContestExam, exam_id, populate_existing=True)
    assert exam.status == ContestExamStatus.failed and "recusou" in exam.error
    assert (
        await client.post(f"/api/v1/admin/contests/{exam_id}/retry", headers=admin_h)
    ).status_code == 204


def test_formato_do_enum():
    assert QuestionFormat("true_false") is QuestionFormat.true_false
