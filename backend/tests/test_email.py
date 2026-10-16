import pytest
from sqlalchemy import select

from app.core.enums import JobStatus
from app.email import client as email_client
from app.email.models import EmailLog
from app.email.service import queue_email
from app.jobs.models import Job
from app.jobs.registry import load_handlers
from app.jobs.runner import process_next

load_handlers()


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_send(to, subject, html):
        calls.append({"to": to, "subject": subject, "html": html})
        return "resend-id-123"

    monkeypatch.setattr(email_client, "send", fake_send)
    return calls


async def _queue(db, **kw):
    defaults = dict(
        to="aluno@example.com",
        type="verify_email",
        subject="Assunto",
        template="verify_email.html",
        context={"name": "Ana", "url": "http://app.test/verificar-email?token=abc"},
    )
    defaults.update(kw)
    log_id = await queue_email(db, **defaults)
    await db.commit()
    return log_id


async def test_template_renderiza_em_portugues_e_escapa_html(db, sent, session_factory):
    await _queue(db, context={"name": "<b>Ana</b>", "url": "http://app.test/x?token=abc"})
    await process_next(session_factory)
    html = sent[0]["html"]
    assert 'lang="pt-BR"' in html
    assert "Confirmar e-mail" in html
    assert "&lt;b&gt;Ana&lt;/b&gt;" in html


async def test_envio_ok_grava_resend_id(db, sent, session_factory):
    log_id = await _queue(db)
    assert await process_next(session_factory)
    assert sent[0]["to"] == "aluno@example.com"
    db.expire_all()
    log = await db.get(EmailLog, log_id)
    assert log.status == "sent"
    assert log.resend_id == "resend-id-123"


async def test_falha_faz_retry_e_registra_falha_final(db, monkeypatch, session_factory):
    async def failing_send(to, subject, html):
        raise RuntimeError("Resend fora do ar")

    monkeypatch.setattr(email_client, "send", failing_send)
    log_id = await _queue(db)
    job_id = await db.scalar(select(Job.id).where(Job.queue == "email.send"))
    await db.execute(Job.__table__.update().where(Job.id == job_id).values(max_attempts=2))
    await db.commit()

    await process_next(session_factory)
    db.expire_all()
    assert (await db.get(Job, job_id)).status == JobStatus.pending
    assert (await db.get(EmailLog, log_id)).status == "queued"

    await db.execute(
        Job.__table__.update().where(Job.id == job_id).values(run_after=Job.created_at)
    )
    await db.commit()
    await process_next(session_factory)
    db.expire_all()
    assert (await db.get(Job, job_id)).status == JobStatus.failed
    log = await db.get(EmailLog, log_id)
    assert log.status == "failed"
    assert "Resend fora do ar" in log.error


async def test_dedupe_key_impede_envio_duplicado(db, sent):
    first = await _queue(db, dedupe_key="reminder:bloco-1:2026-10-14")
    second = await _queue(db, dedupe_key="reminder:bloco-1:2026-10-14")
    assert first is not None
    assert second is None
    jobs = (await db.scalars(select(Job).where(Job.queue == "email.send"))).all()
    assert len(jobs) == 1


async def test_driver_console_nao_chama_resend(monkeypatch):
    called = False

    def boom(*args):
        nonlocal called
        called = True

    monkeypatch.setattr(email_client, "_send_resend", boom)
    assert await email_client.send("a@example.com", "Oi", "<p>oi</p>") is None
    assert called is False
