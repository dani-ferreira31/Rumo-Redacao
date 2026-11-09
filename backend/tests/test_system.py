"""Painel admin: módulos, limites, orçamento, fila, IA e privacidade."""

import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.ai import client as ai_client_module
from app.ai.client import AIClient
from app.ai.config import resolve_task
from app.ai.models import AICredential, AIUsage
from app.ai.types import ModelInfo
from app.core.enums import AIPurpose, JobStatus, UserRole
from app.email.models import EmailLog
from app.jobs.models import Job
from app.jobs.queue import enqueue
from app.modules.system.budget import send_budget_alerts
from app.modules.system.service import record_heartbeat
from app.modules.system.settings import set_setting
from app.modules.users.models import User
from tests.helpers import PASSWORD, auth, register, register_payload

STUDENT_EMAIL = "aluna.privacidade@example.com"
STUDENT_NAME = "Joana Privacidade"


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
    tokens = await register(client, email=STUDENT_EMAIL, name=STUDENT_NAME)
    await db.execute(
        update(User).where(User.email == STUDENT_EMAIL).values(email_verified_at=datetime.now(UTC))
    )
    await db.commit()
    return auth(tokens["access_token"])


async def test_rotas_admin_exigem_admin(client, student_h):
    for path in ("/api/v1/admin/overview", "/api/v1/admin/ai/providers", "/api/v1/admin/costs"):
        assert (await client.get(path, headers=student_h)).status_code == 403


# ---- módulos -------------------------------------------------------------------------


async def test_modulo_desligado_bloqueia_aluno_mas_nao_admin(client, admin_h, student_h):
    assert (await client.get("/api/v1/features")).json()["essays"] is True
    resp = await client.put(
        "/api/v1/admin/settings/features", headers=admin_h, json={"features": {"essays": False}}
    )
    assert resp.status_code == 200
    assert (await client.get("/api/v1/features")).json()["essays"] is False

    resp = await client.get("/api/v1/essays", headers=student_h)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "feature_disabled"
    assert (await client.get("/api/v1/essays", headers=admin_h)).status_code == 200
    # outros módulos continuam
    assert (await client.get("/api/v1/study-plans", headers=student_h)).status_code == 200

    events = (await client.get("/api/v1/admin/events", headers=admin_h)).json()
    assert events[0]["message"] == "Correção de redações: desligado"


async def test_modulo_desconhecido_e_422(client, admin_h):
    resp = await client.put(
        "/api/v1/admin/settings/features", headers=admin_h, json={"features": {"xpto": True}}
    )
    assert resp.status_code == 422


async def test_cadastro_fechado(client, admin_h):
    await client.put(
        "/api/v1/admin/settings/features",
        headers=admin_h,
        json={"features": {"registration": False}},
    )
    resp = await client.post(
        "/api/v1/auth/register", json=register_payload(name="Novo", email="novo@example.com")
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "registration_closed"


# ---- limites e orçamento -------------------------------------------------------------

ESSAY = "\n".join(f"Linha {i} da redação com argumentos sobre o tema." for i in range(1, 21))


async def _send_essay(client, h):
    return await client.post(
        "/api/v1/essays", headers=h, data={"custom_theme": "Tema livre de teste", "text": ESSAY}
    )


async def test_limite_mensal_de_redacoes(client, admin_h, student_h):
    resp = await client.put(
        "/api/v1/admin/settings/limits",
        headers=admin_h,
        json={"essays_per_month": 2, "ai_budget_usd": None},
    )
    assert resp.status_code == 200
    assert (await _send_essay(client, student_h)).status_code == 202
    assert (await _send_essay(client, student_h)).status_code == 202
    resp = await _send_essay(client, student_h)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "essay_limit_reached"
    # admin não tem limite
    for _ in range(3):
        assert (await _send_essay(client, admin_h)).status_code == 202


async def test_professor_tem_limite_proprio_de_redacoes(client, db, admin_h, student_h):
    await client.put(
        "/api/v1/admin/settings/limits",
        headers=admin_h,
        json={"essays_per_month": 1, "teacher_essays_per_month": 3, "ai_budget_usd": None},
    )
    await db.execute(update(User).where(User.email == STUDENT_EMAIL).values(role=UserRole.teacher))
    await db.commit()
    for _ in range(3):
        assert (await _send_essay(client, student_h)).status_code == 202
    assert (await _send_essay(client, student_h)).status_code == 429


async def test_orcamento_estourado_pausa_envios_e_avisa_admin(client, db, admin_h, student_h):
    await client.put(
        "/api/v1/admin/settings/limits",
        headers=admin_h,
        json={"essays_per_month": None, "ai_budget_usd": 1.0},
    )
    db.add(
        AIUsage(
            purpose=AIPurpose.grading, provider="anthropic", model="x", cost_usd=Decimal("0.85")
        )
    )
    await db.commit()
    assert (await _send_essay(client, student_h)).status_code == 202

    await send_budget_alerts(db)
    await send_budget_alerts(db)  # mesmo nível: não repete
    logs = (await db.scalars(select(EmailLog).where(EmailLog.type == "budget_alert"))).all()
    assert len(logs) == 1 and logs[0].dedupe_key.startswith("budget80:")

    db.add(
        AIUsage(purpose=AIPurpose.grading, provider="anthropic", model="x", cost_usd=Decimal("0.2"))
    )
    await db.commit()
    resp = await _send_essay(client, student_h)
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "ai_budget_exceeded"
    await send_budget_alerts(db)
    keys = {
        log.dedupe_key.split(":")[0]
        for log in await db.scalars(select(EmailLog).where(EmailLog.type == "budget_alert"))
    }
    assert keys == {"budget80", "budget100"}

    overview = (await client.get("/api/v1/admin/overview", headers=admin_h)).json()
    assert overview["budget"]["exceeded"] is True
    assert any("Orçamento" in a["message"] for a in overview["alerts"])


# ---- fila e saúde --------------------------------------------------------------------


async def test_fila_esconde_payload_e_mascara_email(client, db, admin_h):
    job_id = (await enqueue(db, "email.send", {"to": STUDENT_EMAIL, "html": "segredo"})).id
    await db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status=JobStatus.failed, last_error=f"Resend recusou {STUDENT_EMAIL}")
    )
    await db.commit()
    body = (await client.get("/api/v1/admin/jobs", headers=admin_h)).json()
    [job] = [j for j in body["jobs"] if j["id"] == job_id]
    assert "payload" not in job
    assert job["last_error"] == "Resend recusou [e-mail]"
    assert {"queue": "email.send", "failed": 1}.items() <= next(
        c for c in body["counts"] if c["queue"] == "email.send"
    ).items()

    assert (
        await client.post(f"/api/v1/admin/jobs/{job_id}/retry", headers=admin_h)
    ).status_code == 204
    job = await db.get(Job, job_id, populate_existing=True)
    assert job.status == JobStatus.pending and job.attempts == 0
    assert (
        await client.post(f"/api/v1/admin/jobs/{job_id}/cancel", headers=admin_h)
    ).status_code == 204
    job = await db.get(Job, job_id, populate_existing=True)
    assert job.status == JobStatus.cancelled
    # cancelado não volta a rodar sozinho, e não dá para cancelar de novo
    assert (
        await client.post(f"/api/v1/admin/jobs/{job_id}/cancel", headers=admin_h)
    ).status_code == 409


async def test_saude_mostra_worker_parado_e_ativo(client, db, admin_h):
    body = (await client.get("/api/v1/admin/system/health", headers=admin_h)).json()
    worker = next(c for c in body["checks"] if c["name"] == "Worker (fila)")
    assert worker["level"] == "error"
    await record_heartbeat(db)
    body = (await client.get("/api/v1/admin/system/health", headers=admin_h)).json()
    worker = next(c for c in body["checks"] if c["name"] == "Worker (fila)")
    assert worker["level"] == "ok"
    assert body["disk_total_gb"] > 0


# ---- IA ------------------------------------------------------------------------------


class _ListingProvider:
    name = "openai"

    async def list_models(self):
        return [ModelInfo("gpt-teste"), ModelInfo("gpt-outro")]


@pytest.fixture
def fake_providers(monkeypatch):
    client = AIClient(
        factories={
            "openai": lambda key: _ListingProvider(),
            "anthropic": lambda key: (_ for _ in ()).throw(
                RuntimeError(f"401 chave {key} inválida")
            ),
        }
    )
    monkeypatch.setattr(ai_client_module, "get_ai_client", lambda: client)
    from app.modules.system import ai_admin

    monkeypatch.setattr(ai_admin, "get_ai_client", lambda: client)
    return client


async def test_chave_exige_senha_fica_criptografada_e_nunca_sai(
    client, db, admin_h, fake_providers
):
    secret = "sk-proj-SEGREDO-1234567890-abcd"
    resp = await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin_h,
        json={"api_key": secret, "password": "senha-errada"},
    )
    assert resp.status_code == 403
    resp = await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin_h,
        json={"api_key": secret, "password": PASSWORD},
    )
    assert resp.status_code == 204

    cred = await db.get(AICredential, "openai")
    assert secret.encode() not in cred.encrypted_key
    body = (await client.get("/api/v1/admin/ai/providers", headers=admin_h)).text
    assert secret not in body and "sk-pro…abcd" in body

    test = (await client.post("/api/v1/admin/ai/providers/openai/test", headers=admin_h)).json()
    assert test["ok"] is True and [m["id"] for m in test["models"]] == ["gpt-teste", "gpt-outro"]
    await db.refresh(cred)
    assert cred.last_test_ok is True

    config = await resolve_task(db, "grading", provider="openai", model="gpt-teste")
    assert config.api_key == secret


async def test_erro_de_teste_nao_vaza_a_chave(client, admin_h, fake_providers):
    secret = "sk-ant-OUTRO-SEGREDO-9999"
    await client.put(
        "/api/v1/admin/ai/providers/anthropic/key",
        headers=admin_h,
        json={"api_key": secret, "password": PASSWORD},
    )
    test = (await client.post("/api/v1/admin/ai/providers/anthropic/test", headers=admin_h)).json()
    assert test["ok"] is False
    assert secret not in test["error"] and "[chave]" in test["error"]
    overview = (await client.get("/api/v1/admin/overview", headers=admin_h)).json()
    assert any("anthropic" in a["message"] for a in overview["alerts"])


async def test_troca_de_modelo_por_tarefa_vale_sem_reiniciar(client, db, admin_h):
    tasks = (await client.get("/api/v1/admin/ai/tasks", headers=admin_h)).json()
    grading = next(t for t in tasks if t["task"] == "grading")
    assert grading["source"] == "env" and grading["provider"] == "fake"

    resp = await client.put(
        "/api/v1/admin/ai/tasks/grading",
        headers=admin_h,
        json={"provider": "google", "model": "gemini-teste", "effort": "high"},
    )
    assert resp.status_code == 200
    config = await resolve_task(db, "grading")
    assert (config.provider, config.model, config.effort) == ("google", "gemini-teste", "high")
    # a transcrição continua no padrão
    assert (await resolve_task(db, "transcription")).provider == "fake"

    resp = await client.put(
        "/api/v1/admin/ai/tasks/grading",
        headers=admin_h,
        json={"provider": "google", "model": "gemini-teste", "effort": "max"},
    )
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "invalid_effort"

    await client.delete("/api/v1/admin/ai/tasks/grading", headers=admin_h)
    assert (await resolve_task(db, "grading")).provider == "fake"


async def test_precos_editaveis_e_modelo_sem_preco(client, db, admin_h):
    await set_setting(
        db, "ai_tasks", {"grading": {"provider": "openai", "model": "gpt-novo", "effort": None}}
    )
    await db.commit()
    rows = (await client.get("/api/v1/admin/ai/prices", headers=admin_h)).json()
    assert {"model": "gpt-novo", "source": "missing"}.items() <= next(
        r for r in rows if r["model"] == "gpt-novo"
    ).items()
    resp = await client.put(
        "/api/v1/admin/ai/prices",
        headers=admin_h,
        json={"prices": [{"model": "gpt-novo", "input": 1.5, "output": 6, "source": "missing"}]},
    )
    row = next(r for r in resp.json() if r["model"] == "gpt-novo")
    assert row["source"] == "panel" and row["output"] == 6


# ---- custos --------------------------------------------------------------------------


async def test_relatorio_de_custos_por_modelo_e_tarefa(client, db, admin_h):
    now = datetime.now(UTC)
    db.add_all(
        [
            AIUsage(
                purpose=AIPurpose.grading,
                provider="openai",
                model="gpt-a",
                input_tokens=10,
                output_tokens=5,
                cost_usd=Decimal("0.5"),
            ),
            AIUsage(
                purpose=AIPurpose.grading,
                provider="openai",
                model="gpt-a",
                input_tokens=10,
                output_tokens=5,
                cost_usd=None,
            ),
            AIUsage(
                purpose=AIPurpose.transcription,
                provider="anthropic",
                model="claude-x",
                cost_usd=Decimal("0.25"),
            ),
            AIUsage(
                purpose=AIPurpose.grading,
                provider="openai",
                model="gpt-a",
                cost_usd=Decimal("9"),
                created_at=now - timedelta(days=60),
            ),
        ]
    )
    await db.commit()
    body = (await client.get("/api/v1/admin/costs?period=30d", headers=admin_h)).json()
    assert body["total_cost_usd"] == 0.75 and body["total_calls"] == 3
    assert body["unknown_cost_calls"] == 1
    gpt = next(m for m in body["by_model"] if m["model"] == "gpt-a")
    assert gpt["calls"] == 2 and gpt["unknown_cost_calls"] == 1 and gpt["input_tokens"] == 20
    assert {p["purpose"] for p in body["by_purpose"]} == {"grading", "transcription"}
    body90 = (await client.get("/api/v1/admin/costs?period=90d", headers=admin_h)).json()
    assert body90["total_cost_usd"] == 9.75


# ---- cota do plano gratuito -----------------------------------------------------------


def _gemini(minutes_ago: float, tokens: int = 1000, model: str = "gemini-3.5-flash-lite"):
    return AIUsage(
        purpose=AIPurpose.grading,
        provider="google",
        model=model,
        input_tokens=tokens,
        output_tokens=200,
        created_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
    )


async def test_cota_gratuita_conta_uso_do_modelo(client, db, admin_h):
    resp = await client.put(
        "/api/v1/admin/ai/quotas",
        headers=admin_h,
        json={
            "quotas": [
                {
                    "provider": "google",
                    "model_match": "flash-lite",
                    "rpm": 4,
                    "tpm": 10000,
                    "rpd": 5,
                }
            ]
        },
    )
    assert resp.status_code == 200
    # 3 no último minuto, 1 mais cedo; outro modelo e outro provedor não contam
    db.add_all([_gemini(0.1), _gemini(0.2), _gemini(0.3, tokens=5000), _gemini(10)])
    db.add(_gemini(0.1, model="gemini-3.8-flash"))
    db.add(AIUsage(purpose=AIPurpose.grading, provider="openai", model="gpt-flash-lite"))
    await db.commit()

    q = (await client.get("/api/v1/admin/ai/quotas", headers=admin_h)).json()["quotas"][0]
    assert q["models"] == ["gemini-3.5-flash-lite"]
    assert q["rpm"] == {"used": 3, "limit": 4, "pct": 75.0}
    assert q["tpm"] == {"used": 7000, "limit": 10000, "pct": 70.0}
    assert q["rpd"]["limit"] == 5
    assert q["rpd"]["used"] in (3, 4)  # a de 10 min atrás pode cair no dia anterior do Pacífico
    assert q["peak_rpm_today"] >= 1
    assert q["level"] in ("ok", "warning")

    db.add_all([_gemini(0.05), _gemini(0.05)])
    await db.commit()
    q = (await client.get("/api/v1/admin/ai/quotas", headers=admin_h)).json()["quotas"][0]
    assert q["level"] == "error"  # 5 de 4 no minuto
    alerts = (await client.get("/api/v1/admin/overview", headers=admin_h)).json()["alerts"]
    assert any("Cota gratuita do dia" in a["message"] for a in alerts)


async def test_cota_padrao_vem_configurada_para_flash_lite(client, admin_h):
    q = (await client.get("/api/v1/admin/ai/quotas", headers=admin_h)).json()["quotas"]
    assert [(r["rule"]["provider"], r["rule"]["model_match"]) for r in q] == [
        ("google", "flash-lite")
    ]


# ---- privacidade ---------------------------------------------------------------------


async def test_nenhuma_rota_admin_devolve_dados_de_aluno(client, db, admin_h, student_h):
    # gera atividade do aluno: redação, e-mails na fila, uso de IA
    await _send_essay(client, student_h)
    student = await db.scalar(select(User).where(User.email == STUDENT_EMAIL))
    db.add(AIUsage(user_id=student.id, purpose=AIPurpose.grading, provider="fake", model="fake"))
    await db.execute(
        update(Job).values(status=JobStatus.failed, last_error=f"falhou {STUDENT_EMAIL}")
    )
    await db.commit()

    paths = [
        "/api/v1/admin/overview",
        "/api/v1/admin/system/health",
        "/api/v1/admin/jobs",
        "/api/v1/admin/jobs?status=failed",
        "/api/v1/admin/events",
        "/api/v1/admin/settings/features",
        "/api/v1/admin/settings/limits",
        "/api/v1/admin/costs",
        "/api/v1/admin/ai/providers",
        "/api/v1/admin/ai/tasks",
        "/api/v1/admin/ai/prices",
        "/api/v1/admin/ai/calibrations",
        "/api/v1/admin/ai/quotas",
        "/api/v1/admin/invites",
        "/api/v1/admin/logs",
        "/api/v1/admin/messages/welcome",
    ]
    forbidden = [STUDENT_EMAIL, STUDENT_NAME, str(student.id), "Linha 1 da redação"]
    for path in paths:
        resp = await client.get(path, headers=admin_h)
        assert resp.status_code == 200, path
        for value in forbidden:
            assert not re.search(re.escape(value), resp.text, re.I), f"{path} expõe {value!r}"


async def test_lista_de_usuarios_mostra_conta_mas_nao_conteudo(client, db, admin_h, student_h):
    """/admin/users é a exceção combinada: nome e e-mail sim, redação e respostas não."""
    await _send_essay(client, student_h)
    resp = await client.get("/api/v1/admin/users", headers=admin_h)
    assert STUDENT_EMAIL in resp.text
    assert "Linha 1 da redação" not in resp.text
    assert "essay" not in resp.text
