from sqlalchemy import update

from app.email import client
from app.email.models import EmailLog
from app.jobs.registry import job_handler


@job_handler("email.send")
async def send_email(session, payload, job) -> None:
    log = await session.get(EmailLog, payload["email_log_id"])
    if log is None or log.status == "sent":
        return  # idempotente: já enviado (ou o log sumiu)
    try:
        provider_id = await client.send(payload["to"], payload["subject"], payload["html"])
    except Exception as exc:
        if job.attempts >= job.max_attempts:
            # última tentativa: registra a falha antes de o job virar `failed`
            await session.execute(
                update(EmailLog)
                .where(EmailLog.id == log.id)
                .values(status="failed", error=f"{type(exc).__name__}: {exc}"[:2000])
            )
            await session.commit()
        raise
    log.status = "sent"
    log.resend_id = provider_id
    log.error = None
