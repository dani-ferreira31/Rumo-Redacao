from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update

from app.modules.questions.models import KnowledgeArea, Question, QuestionAttempt
from app.modules.stats.service import dashboard, streak
from app.modules.users.models import User
from tests.helpers import auth, register


def test_sequencia_de_dias():
    today = date(2026, 10, 15)
    d = lambda n: today - timedelta(days=n)  # noqa: E731
    assert streak(set(), today) == 0
    assert streak({d(0), d(1), d(2)}, today) == 3
    assert streak({d(1), d(2)}, today) == 2  # hoje ainda não estudou: conta até ontem
    assert streak({d(0), d(2)}, today) == 1
    assert streak({d(2), d(3)}, today) == 0


async def test_painel(client, db):
    tokens = await register(client)
    h = auth(tokens["access_token"])
    user = await db.scalar(select(User))
    await db.execute(update(User).values(timezone="America/Manaus"))
    await db.commit()

    plan = (
        await client.post(
            "/api/v1/study-plans",
            headers=h,
            json={"name": "Aulas", "grid_start": "06:00", "grid_end": "23:30"},
        )
    ).json()
    # 2026-10-15 é quinta (weekday 4)
    for start, end in [("08:00", "09:00"), ("20:00", "21:00")]:
        await client.post(
            f"/api/v1/study-plans/{plan['id']}/blocks",
            headers=h,
            json={"weekday": 4, "start_time": start, "end_time": end, "title": "Estudo"},
        )
    area = await db.scalar(select(KnowledgeArea).where(KnowledgeArea.code == "MT"))
    q = Question(year=2023, area_id=area.id, statement_md="x", correct_option="A")
    db.add(q)
    await db.flush()
    # quarta e quinta (horário de Manaus) com atividade
    for when, ok in [
        (datetime(2026, 10, 14, 15, tzinfo=UTC), True),
        (datetime(2026, 10, 15, 15, tzinfo=UTC), False),
    ]:
        db.add(
            QuestionAttempt(
                user_id=user.id,
                question_id=q.id,
                selected_option="A",
                is_correct=ok,
                answered_at=when,
            )
        )
    await db.commit()

    # quinta 2026-10-15 13:00 em Manaus (UTC−4) = 17:00 UTC
    out = await dashboard(db, user, now=datetime(2026, 10, 15, 17, tzinfo=UTC))
    assert out.weekday == 4
    assert [b.start_time.isoformat() for b in out.today_blocks] == ["08:00:00", "20:00:00"]
    assert out.next_block_id == out.today_blocks[1].id  # o das 08:00 já passou
    assert (out.week_accuracy.answered, out.week_accuracy.correct) == (2, 1)
    assert out.streak_days == 2 and out.studied_today

    resp = await client.get("/api/v1/dashboard", headers=h)
    assert resp.status_code == 200
