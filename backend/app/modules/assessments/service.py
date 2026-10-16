"""Provas do professor: montagem com questões do banco, link para os alunos e resultados.

Mesma regra do banco de questões: o aluno só recebe o gabarito depois de entregar a prova.
"""

import secrets
import uuid
from collections import defaultdict

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import QuestionFormat
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.modules.assessments.models import (
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentQuestion,
)
from app.modules.assessments.schemas import (
    AssessmentDetail,
    AssessmentIn,
    AssessmentPublic,
    AssessmentResults,
    AssessmentSummary,
    AssessmentUpdate,
    AttemptInfo,
    AttemptItemResult,
    AttemptOut,
    AttemptRow,
    QuestionResult,
    TeacherQuestion,
)
from app.modules.questions import service as questions
from app.modules.questions.models import KnowledgeArea, Question
from app.modules.questions.schemas import QuestionOut
from app.modules.users.models import User
from app.storage import LocalStorage


def share_url(code: str) -> str:
    return f"{get_settings().app_url}/provas/{code}"


def _pct(correct: int, total: int) -> float | None:
    return round(100 * correct / total, 1) if total else None


# ---- consultas comuns ---------------------------------------------------------------


async def _question_ids(session: AsyncSession, assessment_id: uuid.UUID) -> list[int]:
    rows = await session.scalars(
        select(AssessmentQuestion.question_id)
        .where(AssessmentQuestion.assessment_id == assessment_id)
        .order_by(AssessmentQuestion.position)
    )
    return list(rows)


async def _answer_key(session: AsyncSession, ids: list[int]) -> dict[int, str | None]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Question.id, Question.correct_option).where(Question.id.in_(ids))
    )
    return dict(rows.all())


async def _counts(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int, int]]:
    """(questões, alunos que abriram, alunos que entregaram) por prova."""
    if not ids:
        return {}
    out = {i: [0, 0, 0] for i in ids}
    for aid, n in await session.execute(
        select(AssessmentQuestion.assessment_id, func.count())
        .where(AssessmentQuestion.assessment_id.in_(ids))
        .group_by(AssessmentQuestion.assessment_id)
    ):
        out[aid][0] = n
    for aid, started, finished in await session.execute(
        select(
            AssessmentAttempt.assessment_id,
            func.count(),
            func.count(AssessmentAttempt.finished_at),
        )
        .where(AssessmentAttempt.assessment_id.in_(ids))
        .group_by(AssessmentAttempt.assessment_id)
    ):
        out[aid][1], out[aid][2] = started, finished
    return {k: (v[0], v[1], v[2]) for k, v in out.items()}


def _summary(a: Assessment, counts: tuple[int, int, int]) -> AssessmentSummary:
    return AssessmentSummary(
        id=a.id,
        title=a.title,
        share_code=a.share_code,
        url=share_url(a.share_code),
        is_open=a.is_open,
        question_count=counts[0],
        attempts=counts[1],
        finished=counts[2],
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


async def _owned(session: AsyncSession, teacher: User, assessment_id: uuid.UUID) -> Assessment:
    a = await session.get(Assessment, assessment_id)
    if a is None or a.teacher_id != teacher.id:
        raise NotFoundError("Prova não encontrada.")
    return a


async def _check_questions(session: AsyncSession, teacher: User, ids: list[int]) -> None:
    """Só entram questões publicadas, não anuladas e com gabarito, de trilhas ligadas."""
    rows = (
        await session.execute(
            select(Question.id, KnowledgeArea.code)
            .join(KnowledgeArea, KnowledgeArea.id == Question.area_id)
            .where(
                Question.id.in_(ids),
                Question.is_published.is_(True),
                Question.is_annulled.is_(False),
                Question.correct_option.is_not(None),
            )
        )
    ).all()
    found = {qid for qid, _ in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise AppError(
            "invalid_questions",
            "Algumas questões não existem mais ou foram anuladas. Remova-as da prova.",
            422,
            details={"question_ids": missing},
        )
    for track in {questions.track_of(code) for _, code in rows}:
        await questions.ensure_track(session, teacher, track)


async def _set_questions(session: AsyncSession, assessment_id: uuid.UUID, ids: list[int]) -> None:
    await session.execute(
        delete(AssessmentQuestion).where(AssessmentQuestion.assessment_id == assessment_id)
    )
    session.add_all(
        AssessmentQuestion(assessment_id=assessment_id, question_id=qid, position=pos)
        for pos, qid in enumerate(ids, start=1)
    )


# ---- professor ----------------------------------------------------------------------


async def list_for_teacher(session: AsyncSession, teacher: User) -> list[AssessmentSummary]:
    rows = list(
        await session.scalars(
            select(Assessment)
            .where(Assessment.teacher_id == teacher.id)
            .order_by(Assessment.created_at.desc())
        )
    )
    counts = await _counts(session, [a.id for a in rows])
    return [_summary(a, counts[a.id]) for a in rows]


async def create(
    session: AsyncSession, storage: LocalStorage, teacher: User, data: AssessmentIn
) -> AssessmentDetail:
    await _check_questions(session, teacher, data.question_ids)
    a = Assessment(
        teacher_id=teacher.id,
        title=data.title,
        instructions=(data.instructions or "").strip() or None,
        share_code=secrets.token_urlsafe(6),
    )
    session.add(a)
    await session.flush()
    await _set_questions(session, a.id, data.question_ids)
    await session.commit()
    return await detail(session, storage, teacher, a.id)


async def detail(
    session: AsyncSession, storage: LocalStorage, teacher: User, assessment_id: uuid.UUID
) -> AssessmentDetail:
    a = await _owned(session, teacher, assessment_id)
    await session.refresh(a)
    ids = await _question_ids(session, a.id)
    items = []
    for pos, qid in enumerate(ids, start=1):
        q = await session.get(Question, qid)
        parts = await questions._question_parts(session, q, storage, teacher)
        items.append(
            TeacherQuestion(
                **parts,
                position=pos,
                correct_option=q.correct_option,
                explanation_md=questions.render_assets(q.explanation_md, storage)
                if q.explanation_md
                else None,
            )
        )
    counts = (await _counts(session, [a.id]))[a.id]
    return AssessmentDetail(
        **_summary(a, counts).model_dump(), instructions=a.instructions, questions=items
    )


async def update(
    session: AsyncSession,
    storage: LocalStorage,
    teacher: User,
    assessment_id: uuid.UUID,
    data: AssessmentUpdate,
) -> AssessmentDetail:
    a = await _owned(session, teacher, assessment_id)
    fields = data.model_dump(exclude_unset=True)
    if fields.get("question_ids") is not None:
        started = await session.scalar(
            select(func.count())
            .select_from(AssessmentAttempt)
            .where(AssessmentAttempt.assessment_id == a.id)
        )
        if started:
            raise AppError(
                "assessment_has_attempts",
                "Alunos já abriram esta prova: as questões não podem mais mudar. "
                "Crie uma prova nova para outra versão.",
                409,
            )
        await _check_questions(session, teacher, fields["question_ids"])
        await _set_questions(session, a.id, fields["question_ids"])
    if fields.get("title") is not None:
        a.title = fields["title"]
    if "instructions" in fields:
        a.instructions = (fields["instructions"] or "").strip() or None
    if fields.get("is_open") is not None:
        a.is_open = fields["is_open"]
    a.updated_at = utcnow()
    await session.commit()
    return await detail(session, storage, teacher, a.id)


async def remove(session: AsyncSession, teacher: User, assessment_id: uuid.UUID) -> None:
    a = await _owned(session, teacher, assessment_id)
    await session.delete(a)
    await session.commit()


async def _answers_by_attempt(
    session: AsyncSession, attempt_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[int, str]]:
    out: dict[uuid.UUID, dict[int, str]] = defaultdict(dict)
    if attempt_ids:
        for att, qid, opt in await session.execute(
            select(
                AssessmentAnswer.attempt_id,
                AssessmentAnswer.question_id,
                AssessmentAnswer.selected_option,
            ).where(AssessmentAnswer.attempt_id.in_(attempt_ids))
        ):
            out[att][qid] = opt
    return out


async def results(
    session: AsyncSession, teacher: User, assessment_id: uuid.UUID
) -> AssessmentResults:
    a = await _owned(session, teacher, assessment_id)
    ids = await _question_ids(session, a.id)
    key = await _answer_key(session, ids)
    rows = (
        await session.execute(
            select(AssessmentAttempt, User.name, User.email)
            .join(User, User.id == AssessmentAttempt.user_id)
            .where(AssessmentAttempt.assessment_id == a.id)
            .order_by(User.name)
        )
    ).all()
    answers = await _answers_by_attempt(session, [att.id for att, _, _ in rows])

    attempts = []
    for att, name, email in rows:
        mine = answers.get(att.id, {})
        correct = att.correct if att.finished_at else None
        attempts.append(
            AttemptRow(
                id=att.id,
                student_name=name,
                student_email=email,
                started_at=att.started_at,
                finished_at=att.finished_at,
                answered=len(mine),
                correct=correct,
                total=len(ids),
                pct=_pct(correct, len(ids)) if correct is not None else None,
                answers=mine,
            )
        )

    # acerto por questão: só quem entregou (prova em andamento ainda pode mudar)
    finished_ids = {att.id for att, _, _ in rows if att.finished_at}
    per_question = []
    for pos, qid in enumerate(ids, start=1):
        dist: dict[str, int] = defaultdict(int)
        for att_id in finished_ids:
            opt = answers.get(att_id, {}).get(qid)
            if opt:
                dist[opt] += 1
        answered = sum(dist.values())
        correct = dist.get(key.get(qid) or "", 0)
        per_question.append(
            QuestionResult(
                question_id=qid,
                position=pos,
                correct_option=key.get(qid),
                answered=answered,
                correct=correct,
                pct=_pct(correct, answered),
                distribution=dict(dist),
            )
        )
    done = [r.pct for r in attempts if r.pct is not None]
    return AssessmentResults(
        assessment_id=a.id,
        total_questions=len(ids),
        attempts=attempts,
        finished=len(done),
        avg_pct=round(sum(done) / len(done), 1) if done else None,
        questions=per_question,
    )


# ---- aluno --------------------------------------------------------------------------


async def _by_code(session: AsyncSession, code: str) -> Assessment:
    a = await session.scalar(select(Assessment).where(Assessment.share_code == code.strip()))
    if a is None:
        raise NotFoundError("Prova não encontrada. Confira o link com o professor.")
    return a


async def _my_attempt(
    session: AsyncSession, user: User, assessment_id: uuid.UUID
) -> AssessmentAttempt | None:
    return await session.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.assessment_id == assessment_id, AssessmentAttempt.user_id == user.id
        )
    )


def _info(att: AssessmentAttempt) -> AttemptInfo:
    return AttemptInfo(
        id=att.id,
        started_at=att.started_at,
        finished_at=att.finished_at,
        correct=att.correct if att.finished_at else None,
        total=att.total if att.finished_at else None,
    )


async def public_info(session: AsyncSession, user: User, code: str) -> AssessmentPublic:
    a = await _by_code(session, code)
    teacher_name = await session.scalar(select(User.name).where(User.id == a.teacher_id))
    att = await _my_attempt(session, user, a.id)
    return AssessmentPublic(
        title=a.title,
        instructions=a.instructions,
        teacher_name=teacher_name or "",
        question_count=len(await _question_ids(session, a.id)),
        is_open=a.is_open,
        attempt=_info(att) if att else None,
    )


async def _attempt_out(
    session: AsyncSession, storage: LocalStorage, user: User, att: AssessmentAttempt
) -> AttemptOut:
    a = await session.get(Assessment, att.assessment_id)
    ids = await _question_ids(session, a.id)
    mine = (await _answers_by_attempt(session, [att.id])).get(att.id, {})
    items: list[QuestionOut] = []
    result: list[AttemptItemResult] | None = [] if att.finished_at else None
    for qid in ids:
        q = await session.get(Question, qid)
        items.append(QuestionOut(**await questions._question_parts(session, q, storage, user)))
        if result is not None:
            selected = mine.get(qid)
            result.append(
                AttemptItemResult(
                    question_id=qid,
                    selected_option=selected,
                    correct_option=q.correct_option,
                    is_correct=selected is not None and selected == q.correct_option,
                    explanation_md=questions.render_assets(q.explanation_md, storage)
                    if q.explanation_md
                    else None,
                )
            )
    return AttemptOut(
        attempt=_info(att),
        title=a.title,
        instructions=a.instructions,
        is_open=a.is_open,
        questions=items,
        answers=mine,
        result=result,
    )


async def start(session: AsyncSession, storage: LocalStorage, user: User, code: str) -> AttemptOut:
    """Começa (ou retoma) a prova. Cada aluno tem uma tentativa só."""
    a = await _by_code(session, code)
    att = await _my_attempt(session, user, a.id)
    if att is None:
        if not a.is_open:
            raise AppError(
                "assessment_closed", "Esta prova não está aberta para respostas agora.", 409
            )
        await session.execute(
            insert(AssessmentAttempt)
            .values(assessment_id=a.id, user_id=user.id)
            .on_conflict_do_nothing(index_elements=["assessment_id", "user_id"])
        )
        await session.commit()
        att = await _my_attempt(session, user, a.id)
    return await _attempt_out(session, storage, user, att)


async def _owned_attempt(
    session: AsyncSession, user: User, attempt_id: uuid.UUID
) -> AssessmentAttempt:
    att = await session.get(AssessmentAttempt, attempt_id)
    if att is None or att.user_id != user.id:
        raise NotFoundError("Prova não encontrada.")
    return att


async def get_attempt(
    session: AsyncSession, storage: LocalStorage, user: User, attempt_id: uuid.UUID
) -> AttemptOut:
    return await _attempt_out(
        session, storage, user, await _owned_attempt(session, user, attempt_id)
    )


async def save_answer(
    session: AsyncSession, user: User, attempt_id: uuid.UUID, question_id: int, letter: str | None
) -> None:
    att = await _owned_attempt(session, user, attempt_id)
    if att.finished_at is not None:
        raise AppError("assessment_finished", "Você já entregou esta prova.", 409)
    a = await session.get(Assessment, att.assessment_id)
    if not a.is_open:
        raise AppError("assessment_closed", "O professor fechou esta prova.", 409)
    if question_id not in await _question_ids(session, a.id):
        raise AppError("question_not_in_assessment", "A questão não faz parte desta prova.", 422)
    if letter is None:
        await session.execute(
            delete(AssessmentAnswer).where(
                AssessmentAnswer.attempt_id == att.id, AssessmentAnswer.question_id == question_id
            )
        )
    else:
        fmt = await session.scalar(select(Question.format).where(Question.id == question_id))
        if fmt == QuestionFormat.true_false and letter not in ("C", "E"):
            raise AppError("invalid_option", "Responda Certo (C) ou Errado (E).", 422)
        stmt = insert(AssessmentAnswer).values(
            attempt_id=att.id, question_id=question_id, selected_option=letter
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["attempt_id", "question_id"],
                set_={"selected_option": stmt.excluded.selected_option, "answered_at": func.now()},
            )
        )
    await session.commit()


async def finish(
    session: AsyncSession, storage: LocalStorage, user: User, attempt_id: uuid.UUID
) -> AttemptOut:
    """Entrega a prova: calcula a nota e libera o gabarito para o aluno."""
    att = await _owned_attempt(session, user, attempt_id)
    if att.finished_at is None:
        ids = await _question_ids(session, att.assessment_id)
        mine = (await _answers_by_attempt(session, [att.id])).get(att.id, {})
        key = await _answer_key(session, ids)
        att.correct = sum(1 for qid in ids if mine.get(qid) and mine[qid] == key.get(qid))
        att.total = len(ids)
        att.finished_at = utcnow()
        await session.commit()
    return await _attempt_out(session, storage, user, att)
