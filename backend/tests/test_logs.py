"""Admin → Logs: avisos e erros gravados sem dados pessoais, com retenção."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.core import applog
from app.core.enums import UserRole
from app.core.logging import bind_log_context, clear_log_context
from app.modules.system.models import AppLog
from app.modules.users.models import User
from tests.helpers import auth, register

EMAIL = "aluna.secreta@example.com"


@pytest.fixture
async def admin_h(client, db):
    tokens = await register(client, email="admin@example.com", name="Admin")
    await db.execute(
        update(User).where(User.email == "admin@example.com").values(role=UserRole.admin)
    )
    await db.commit()
    return auth(tokens["access_token"])


def test_scrub_remove_dados_pessoais():
    text = (
        f"falhou para {EMAIL} com Bearer abc.def.ghi, token eyJhbGciOi.eyJzdWIi.c2ln, "
        "chave APP_USR-1234567890123456-abcdef, CPF 123.456.789-09 e tel (11) 98765-4321"
    )
    out = applog.scrub_text(text)
    for leaked in (EMAIL, "abc.def.ghi", "eyJhbGciOi", "APP_USR-123", "123.456.789-09", "98765"):
        assert leaked not in out
    assert "[e-mail]" in out and "[cpf]" in out

    data = applog.scrub(
        {
            "password": "x",
            "user_id": "u-1",
            "transcription_text": "texto do aluno",
            "name": "Joana",
            "essay_id": "e-1",
            "job_id": 7,
            "nested": {"api_key": "k", "status": 502, "msg": f"para {EMAIL}"},
            "description": "fica",
        }
    )
    assert data["password"] == data["user_id"] == data["transcription_text"] == "[removido]"
    assert data["name"] == "[removido]"
    assert data["essay_id"] == "e-1" and data["job_id"] == 7
    assert data["nested"] == {"api_key": "[removido]", "status": 502, "msg": "para [e-mail]"}
    assert data["description"] == "fica"


async def test_erros_sao_gravados_sem_dados_pessoais(client, db, admin_h):
    applog.install("api")
    log = logging.getLogger("app.teste")
    clear_log_context()
    bind_log_context(request_id="req-123", path="/api/v1/essays", essay_id="e-9")
    try:
        raise ValueError(f"não achei o usuário {EMAIL}")
    except ValueError:
        log.exception("essay_grade_failed", extra={"extra_fields": {"email": EMAIL, "attempt": 2}})
    log.warning("ai_retry", extra={"extra_fields": {"provider": "google"}})
    log.info("so_info_nao_entra")
    logging.getLogger("httpx").warning("biblioteca ignorada")
    clear_log_context()
    assert await applog.flush_logs(db) == 2

    page = (await client.get("/api/v1/admin/logs", headers=admin_h)).json()
    assert EMAIL not in str(page)
    first, second = page["items"]  # mais recente primeiro
    assert second["event"] == "essay_grade_failed"
    assert second["level"] == "ERROR"
    assert second["error"] == "ValueError: não achei o usuário [e-mail]"
    assert second["path"] == "/api/v1/essays"
    assert second["request_id"] == "req-123"
    assert first["event"] == "ai_retry"
    assert page["summary"]["errors_24h"] == 1 and page["summary"]["warnings_24h"] == 1
    assert page["summary"]["top_24h"][0]["error"] == "ValueError"
    assert page["retention_days"] == 30

    detail = (await client.get(f"/api/v1/admin/logs/{second['id']}", headers=admin_h)).json()
    assert "Traceback" in detail["traceback"] and EMAIL not in detail["traceback"]
    assert detail["details"]["email"] == "[removido]"
    assert detail["details"]["essay_id"] == "e-9"

    errors = (await client.get("/api/v1/admin/logs?level=ERROR", headers=admin_h)).json()
    assert [i["event"] for i in errors["items"]] == ["essay_grade_failed"]
    found = (await client.get("/api/v1/admin/logs?q=ai_retry", headers=admin_h)).json()
    assert [i["event"] for i in found["items"]] == ["ai_retry"]


async def test_retencao_e_limpeza(client, db, admin_h):
    now = datetime.now(UTC)
    for days in (1, 10, 40):
        db.add(
            AppLog(
                created_at=now - timedelta(days=days),
                level="ERROR",
                source="worker",
                logger="app.x",
                event=f"antigo_{days}",
            )
        )
    await db.commit()
    assert await applog.purge_old_logs(db, 30) == 1

    resp = await client.put(
        "/api/v1/admin/logs/settings", headers=admin_h, json={"retention_days": 7}
    )
    assert resp.json() == {"retention_days": 7}
    assert await db.scalar(select(func.count()).select_from(AppLog)) == 1
    page = (await client.get("/api/v1/admin/logs", headers=admin_h)).json()
    assert page["retention_days"] == 7

    assert (await client.delete("/api/v1/admin/logs", headers=admin_h)).status_code == 204
    assert await db.scalar(select(func.count()).select_from(AppLog)) == 0
    events = (await client.get("/api/v1/admin/events", headers=admin_h)).json()
    assert "Logs apagados pelo admin (1 registros)" in [e["message"] for e in events]


async def test_logs_exigem_admin(client):
    h = auth((await register(client))["access_token"])
    assert (await client.get("/api/v1/admin/logs", headers=h)).status_code == 403
    assert (await client.delete("/api/v1/admin/logs", headers=h)).status_code == 403


def test_log_do_stdout_tambem_sai_sem_dados_pessoais():
    from app.core.logging import JsonFormatter

    record = logging.LogRecord("app.x", logging.WARNING, __file__, 1, "falha", None, None)
    record.extra_fields = {"email": EMAIL, "error": f"erro com {EMAIL}", "status": 500}
    out = JsonFormatter().format(record)
    assert EMAIL not in out
    assert '"status": 500' in out
