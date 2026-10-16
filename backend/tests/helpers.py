import re
from datetime import date

from sqlalchemy import select

from app.jobs.models import Job

PASSWORD = "senha-forte-123"
# convite de aluno sem limite, criado pela fixture `client` (conftest)
INVITE_CODE = "convite-de-teste"


def register_payload(**overrides) -> dict:
    data = {
        "invite_code": INVITE_CODE,
        "name": "Maria Souza",
        "email": "maria@example.com",
        "password": PASSWORD,
        "birth_date": "2000-05-10",
    }
    data.update(overrides)
    return data


def minor_birth_date() -> str:
    today = date.today()
    return date(today.year - 16, 1, 1).isoformat()


async def register(client, **overrides) -> dict:
    resp = await client.post("/api/v1/auth/register", json=register_payload(**overrides))
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def email_jobs(db, to: str | None = None) -> list[Job]:
    db.expire_all()
    jobs = (await db.scalars(select(Job).where(Job.queue == "email.send").order_by(Job.id))).all()
    return [j for j in jobs if to is None or j.payload["to"] == to]


async def last_email_token(db, path: str) -> str:
    """Extrai o token do último e-mail enfileirado com link para `path`."""
    for job in reversed(await email_jobs(db)):
        match = re.search(rf"{path}\?token=([\w-]+)", job.payload["html"])
        if match:
            return match.group(1)
    raise AssertionError(f"nenhum e-mail com link para {path}")
