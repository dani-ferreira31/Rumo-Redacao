import io
from datetime import UTC, datetime

import cv2
import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select, update

from app.ai.models import AIUsage
from app.core.enums import EssayStatus
from app.jobs.models import Job
from app.jobs.registry import load_handlers
from app.jobs.runner import process_next
from app.modules.essays.models import Essay, EssayGradingRun, EssayResult, EssayTheme
from app.modules.users.models import User
from app.storage import get_storage
from tests.helpers import auth, register

load_handlers()

ESSAY = "\n".join(
    f"Linha {i} da redação, com argumentos sobre o tema proposto e algumas ideias."
    for i in range(1, 21)
)


@pytest.fixture
async def user_token(client, db):
    tokens = await register(client)
    await db.execute(update(User).values(email_verified_at=datetime.now(UTC)))
    await db.commit()
    return tokens["access_token"]


@pytest.fixture
async def theme(db):
    t = EssayTheme(
        title="Desafios para a valorização da herança africana no Brasil",
        year=2024,
        is_official=True,
    )
    db.add(t)
    await db.commit()
    return t


def _photo_bytes() -> bytes:
    img = np.full((1200, 900, 3), 240, np.uint8)
    for y in range(100, 1100, 40):
        cv2.line(img, (60, y), (840, y), (70, 70, 70), 2)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "JPEG")
    return buf.getvalue()


async def _drain(session_factory):
    while await process_next(session_factory):
        pass


async def _get(client, token, essay_id):
    resp = await client.get(f"/api/v1/essays/{essay_id}", headers=auth(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_temas_oficiais(client, user_token, theme):
    resp = await client.get("/api/v1/essay-themes", headers=auth(user_token))
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert theme.title in titles
    # o mais recente vem primeiro: 2026, da migration 0007
    assert titles[0].startswith("A valorização do Sistema Único de Saúde")


async def test_email_nao_verificado_nao_envia(client):
    tokens = await register(client)
    resp = await client.post(
        "/api/v1/essays",
        headers=auth(tokens["access_token"]),
        data={"custom_theme": "Tema livre de teste", "text": ESSAY},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "email_not_verified"


async def test_validacoes_do_envio(client, user_token, theme):
    h = auth(user_token)
    resp = await client.post("/api/v1/essays", headers=h, data={"text": ESSAY})
    assert resp.json()["error"]["code"] == "theme_required"
    resp = await client.post("/api/v1/essays", headers=h, data={"theme_id": str(theme.id)})
    assert resp.json()["error"]["code"] == "content_required"
    resp = await client.post(
        "/api/v1/essays",
        headers=h,
        data={"theme_id": str(theme.id)},
        files={"images": ("x.jpg", b"nao e imagem", "image/jpeg")},
    )
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "invalid_image"
    files = [("images", (f"p{i}.jpg", _photo_bytes(), "image/jpeg")) for i in range(3)]
    resp = await client.post(
        "/api/v1/essays", headers=h, data={"theme_id": str(theme.id)}, files=files
    )
    assert resp.json()["error"]["code"] == "too_many_images"


async def test_fluxo_texto_digitado_ate_a_nota(client, db, session_factory, user_token, theme):
    h = auth(user_token)
    resp = await client.post(
        "/api/v1/essays", headers=h, data={"theme_id": str(theme.id), "text": ESSAY}
    )
    assert resp.status_code == 202, resp.text
    essay = resp.json()
    assert essay["status"] == "grading" and essay["input_type"] == "text"

    await _drain(session_factory)
    essay = await _get(client, user_token, essay["id"])
    assert essay["status"] == "graded"
    result = essay["result"]
    assert result["simulated"] is True
    assert len(result["competencies"]) == 5
    assert result["total"] == sum(result["scores"])
    assert all(s % 20 == 0 for s in result["scores"])
    assert set(result["c5_elements"]) == {"agente", "acao", "meio", "finalidade", "detalhamento"}

    runs = (await db.scalars(select(EssayGradingRun))).all()
    assert len(runs) == 2 and {r.prompt_version for r in runs} == {
        "correcao-v1+rubrica-enem-2025-v1"
    }
    usage = (await db.scalars(select(AIUsage))).all()
    assert len(usage) == 2
    email_jobs = (await db.scalars(select(Job).where(Job.queue == "email.send"))).all()
    assert any("redacoes/" + essay["id"] in j.payload["html"] for j in email_jobs)

    stats = (await client.get("/api/v1/essays/stats", headers=h)).json()
    assert stats["points"][0]["total"] == result["total"]
    page = (await client.get("/api/v1/essays", headers=h)).json()
    assert page["items"][0]["total"] == result["total"]


async def test_texto_curto_e_anulado_sem_chamar_ia(client, db, session_factory, user_token):
    text = "\n\n".join(" ".join(["palavra"] * 30) for _ in range(2))  # ~6 linhas
    resp = await client.post(
        "/api/v1/essays",
        headers=auth(user_token),
        data={"custom_theme": "Tema livre de teste", "text": text},
    )
    await _drain(session_factory)
    essay = await _get(client, user_token, resp.json()["id"])
    assert essay["result"]["annulled"] is True
    assert essay["result"]["zero_reason"] == "texto_insuficiente"
    assert essay["result"]["total"] == 0
    assert (await db.scalars(select(AIUsage))).all() == []


async def test_fluxo_foto_revisao_e_confirmacao(client, db, session_factory, user_token, theme):
    h = auth(user_token)
    resp = await client.post(
        "/api/v1/essays",
        headers=h,
        data={"theme_id": str(theme.id)},
        files={"images": ("folha.jpg", _photo_bytes(), "image/jpeg")},
    )
    assert resp.status_code == 202, resp.text
    essay_id = resp.json()["id"]
    assert resp.json()["status"] == "uploaded"

    await _drain(session_factory)
    essay = await _get(client, user_token, essay_id)
    assert essay["status"] == "awaiting_review"
    assert essay["images"][0]["url"] and essay["images"][0]["original_url"]
    assert essay["transcription"]["confidence"] == "media"
    text = essay["transcription_text"]
    assert "[ilegível]" in text and "[?IBGE]" in text

    # a imagem pré-processada é servida pela URL assinada
    img = await client.get(essay["images"][0]["url"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"

    # confirmar com marcadores pendentes é bloqueado
    resp = await client.post(f"/api/v1/essays/{essay_id}/confirm", headers=h)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "unresolved_markers"
    assert [m["line"] for m in resp.json()["error"]["details"]["markers"]] == [
        9,
        16,
    ]  # linhas da caixa de texto (com as linhas em branco)

    fixed = text.replace("[?IBGE]", "IBGE").replace("[ilegível]", "no")
    resp = await client.put(
        f"/api/v1/essays/{essay_id}/transcription", headers=h, json={"text": fixed}
    )
    assert resp.status_code == 200
    resp = await client.post(f"/api/v1/essays/{essay_id}/confirm", headers=h)
    assert resp.status_code == 200 and resp.json()["status"] == "grading"

    # revisar depois de confirmar não é permitido
    resp = await client.put(
        f"/api/v1/essays/{essay_id}/transcription", headers=h, json={"text": "x"}
    )
    assert resp.status_code == 409

    await _drain(session_factory)
    essay = await _get(client, user_token, essay_id)
    assert essay["status"] == "graded"
    assert essay["line_count"] == 18


async def test_falha_e_retry(client, db, session_factory, user_token, theme, monkeypatch):
    from app.ai.client import AIError
    from app.modules.essays import jobs

    async def broken(*args, **kwargs):
        raise AIError("simulada")

    monkeypatch.setattr(jobs, "grade_once", broken)
    h = auth(user_token)
    resp = await client.post(
        "/api/v1/essays", headers=h, data={"theme_id": str(theme.id), "text": ESSAY}
    )
    essay_id = resp.json()["id"]
    await _drain(session_factory)
    essay = await _get(client, user_token, essay_id)
    assert essay["status"] == "failed"
    assert essay["error_message"]

    monkeypatch.undo()
    resp = await client.post(f"/api/v1/essays/{essay_id}/retry", headers=h)
    assert resp.status_code == 200 and resp.json()["status"] == "grading"
    await _drain(session_factory)
    assert (await _get(client, user_token, essay_id))["status"] == "graded"


async def test_redacao_de_outro_usuario_e_404(client, db, user_token, theme):
    resp = await client.post(
        "/api/v1/essays",
        headers=auth(user_token),
        data={"theme_id": str(theme.id), "text": ESSAY},
    )
    essay_id = resp.json()["id"]
    other = await register(client, email="outro@example.com")
    resp = await client.get(f"/api/v1/essays/{essay_id}", headers=auth(other["access_token"]))
    assert resp.status_code == 404


async def test_excluir_redacao_apaga_imagens(client, db, session_factory, user_token, theme):
    h = auth(user_token)
    resp = await client.post(
        "/api/v1/essays",
        headers=h,
        data={"theme_id": str(theme.id)},
        files={"images": ("folha.jpg", _photo_bytes(), "image/jpeg")},
    )
    essay_id = resp.json()["id"]
    await _drain(session_factory)
    essay = await db.get(Essay, essay_id)
    user_id = essay.user_id
    folder = get_storage().path_for(f"users/{user_id}/essays/{essay_id}")
    assert folder.exists()

    resp = await client.delete(f"/api/v1/essays/{essay_id}", headers=h)
    assert resp.status_code == 204
    assert not folder.exists()
    db.expire_all()
    assert await db.get(Essay, essay_id) is None
    assert await db.scalar(select(EssayResult)) is None
    assert EssayStatus  # noqa: B018
