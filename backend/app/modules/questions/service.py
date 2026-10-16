"""Banco de questões: catálogo, listagem com filtros, resposta, favoritos,
sessões de prática e estatísticas.

Regra central: o gabarito NUNCA sai num payload antes de a resposta ser
registrada (e, em lista/simulado, só depois de encerrar a sessão).
"""

import base64
import re
import uuid
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import Select, delete, exists, func, literal_column, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PracticeMode, QuestionFormat, UserRole
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.modules.contests.models import ContestExam, ContestExamQuestion
from app.modules.questions.models import (
    Exam,
    ExamQuestion,
    KnowledgeArea,
    PracticeSession,
    Question,
    QuestionAttempt,
    QuestionBookmark,
    QuestionOption,
    QuestionTopic,
    Subject,
    Topic,
)
from app.modules.questions.schemas import (
    AdminQuestionOut,
    AdminQuestionUpdate,
    AnswerIn,
    AnswerOut,
    AreaOut,
    AreaScore,
    ExamPosition,
    GroupScore,
    OptionOut,
    PracticeSessionIn,
    PracticeSessionOut,
    QuestionFilters,
    QuestionListItem,
    QuestionOut,
    QuestionPage,
    QuestionStatsOut,
    SessionItemResult,
    SessionResult,
    SubjectOut,
    SubjectRef,
    TimelinePoint,
    TopicOut,
)
from app.modules.system.settings import FEATURES, feature_enabled
from app.modules.users.models import User
from app.storage import LocalStorage

CONTEST_AREA = "CP"
TRACK_FEATURE = {"enem": "questions_enem", "concurso": "questions_concursos"}

# Faixas de dificuldade pelo parâmetro b da TRI (docs/03). Calibrar com a distribuição real.
EASY_MAX = Decimal("0.5")
HARD_MIN = Decimal("1.5")

# Imagens ficam no markdown como ![alt](asset:<storage_key>) e viram URL assinada na saída.
ASSET_RE = re.compile(r"\(asset:([^)\s]+)\)")
_MD_STRIP_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|[*_`#>\[\]]")


def _tsquery(q: str):
    """Consulta de busca na configuração pt_unaccent (português sem acentos)."""
    return func.websearch_to_tsquery(literal_column("'pt_unaccent'::regconfig"), q)


def difficulty_of(irt_b: Decimal | None) -> str | None:
    if irt_b is None:
        return None
    if irt_b < EASY_MAX:
        return "facil"
    if irt_b > HARD_MIN:
        return "dificil"
    return "media"


def render_assets(md: str, storage: LocalStorage) -> str:
    return ASSET_RE.sub(lambda m: f"({storage.signed_url(m.group(1), expires_in=6 * 3600)})", md)


def preview(md: str, size: int = 220) -> str:
    plain = " ".join(_MD_STRIP_RE.sub(" ", md).split())
    return plain if len(plain) <= size else plain[: size - 1].rstrip() + "…"


# ---- catálogo -------------------------------------------------------------------


async def catalog(session: AsyncSession) -> list[AreaOut]:
    areas = (await session.scalars(select(KnowledgeArea).order_by(KnowledgeArea.id))).all()
    subjects = (await session.scalars(select(Subject).order_by(Subject.name))).all()
    topics = (await session.scalars(select(Topic).order_by(Topic.name))).all()
    topics_by_subject: dict[int, list[TopicOut]] = defaultdict(list)
    for t in topics:
        topics_by_subject[t.subject_id].append(
            TopicOut(id=t.id, name=t.name, slug=t.slug, parent_id=t.parent_id)
        )
    subjects_by_area: dict[int, list[SubjectOut]] = defaultdict(list)
    for s in subjects:
        subjects_by_area[s.area_id].append(
            SubjectOut(id=s.id, name=s.name, slug=s.slug, topics=topics_by_subject[s.id])
        )
    return [
        AreaOut(id=a.id, code=a.code, name=a.name, subjects=subjects_by_area[a.id]) for a in areas
    ]


# ---- filtros --------------------------------------------------------------------


def _last_attempt_subquery(user_id: uuid.UUID):
    """Última tentativa do usuário em cada questão."""
    return (
        select(QuestionAttempt.question_id, QuestionAttempt.is_correct)
        .where(QuestionAttempt.user_id == user_id)
        .ext(distinct_on(QuestionAttempt.question_id))
        .order_by(
            QuestionAttempt.question_id,
            QuestionAttempt.answered_at.desc(),
            QuestionAttempt.id.desc(),
        )
        .subquery("last_attempt")
    )


def _contest_area_id():
    return select(KnowledgeArea.id).where(KnowledgeArea.code == CONTEST_AREA).scalar_subquery()


def track_of(area_code: str) -> str:
    return "concurso" if area_code == CONTEST_AREA else "enem"


async def ensure_track(session: AsyncSession, user: User, track: str) -> None:
    """Módulo ENEM ou Concursos desligado no painel: bloqueia (o admin passa)."""
    name = TRACK_FEATURE[track]
    if user.role != UserRole.admin and not await feature_enabled(session, name):
        raise AppError(
            "feature_disabled",
            f"{FEATURES[name]} está temporariamente indisponível.",
            503,
            details={"feature": name},
        )


def _contest_filter(f: QuestionFilters):
    """Questão pertence a uma prova de concurso que bate com os filtros."""
    conds = [ContestExamQuestion.question_id == Question.id]
    if f.contest_exam_id:
        conds.append(ContestExamQuestion.contest_exam_id == f.contest_exam_id)
    exam_conds = []
    if f.board:
        exam_conds.append(func.lower(ContestExam.board) == f.board.lower())
    if f.organization:
        exam_conds.append(func.lower(ContestExam.organization) == f.organization.lower())
    if f.position:
        exam_conds.append(func.lower(ContestExam.position) == f.position.lower())
    if f.level:
        exam_conds.append(ContestExam.level == f.level)
    if exam_conds:
        conds.append(ContestExamQuestion.contest_exam_id == ContestExam.id)
        conds.extend(exam_conds)
    return exists().where(*conds) if len(conds) > 1 else None


def apply_filters(stmt: Select, f: QuestionFilters, user: User) -> Select:
    stmt = stmt.where(Question.is_annulled.is_(False), Question.is_published.is_(True))
    if f.track == "concurso":
        stmt = stmt.where(Question.area_id == _contest_area_id())
        contest = _contest_filter(f)
        if contest is not None:
            stmt = stmt.where(contest)
        if f.format:
            stmt = stmt.where(Question.format == f.format)
    else:
        stmt = stmt.where(Question.area_id != _contest_area_id())
    if f.area and f.track == "enem":
        stmt = stmt.where(
            Question.area_id
            == select(KnowledgeArea.id)
            .where(KnowledgeArea.code == f.area.upper())
            .scalar_subquery()
        )
    if f.subject_id:
        stmt = stmt.where(Question.subject_id == f.subject_id)
    if f.topic_id:
        stmt = stmt.where(
            exists().where(
                QuestionTopic.question_id == Question.id, QuestionTopic.topic_id == f.topic_id
            )
        )
    if f.year:
        stmt = stmt.where(Question.year == f.year)
    if f.difficulty == "facil":
        stmt = stmt.where(Question.irt_b < EASY_MAX)
    elif f.difficulty == "media":
        stmt = stmt.where(Question.irt_b.between(EASY_MAX, HARD_MIN))
    elif f.difficulty == "dificil":
        stmt = stmt.where(Question.irt_b > HARD_MIN)
    if f.skill:
        stmt = stmt.where(Question.skill_code == f.skill)
    if f.language:
        # questões de língua estrangeira só do idioma escolhido; as demais continuam
        stmt = stmt.where(
            (Question.foreign_language.is_(None)) | (Question.foreign_language == f.language)
        )
    if f.status == "nao_respondidas":
        stmt = stmt.where(
            ~exists().where(
                QuestionAttempt.user_id == user.id, QuestionAttempt.question_id == Question.id
            )
        )
    elif f.status == "erradas":
        last = _last_attempt_subquery(user.id)
        stmt = stmt.where(
            exists().where(last.c.question_id == Question.id, last.c.is_correct.is_(False))
        )
    elif f.status == "favoritas":
        stmt = stmt.where(
            exists().where(
                QuestionBookmark.user_id == user.id, QuestionBookmark.question_id == Question.id
            )
        )
    if f.q and f.q.strip():
        stmt = stmt.where(Question.search_vector.op("@@")(_tsquery(f.q)))
    return stmt


def _encode_offset(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode()).decode()))
    except ValueError as exc:
        raise AppError("invalid_cursor", "Cursor de paginação inválido.", 422) from exc


async def list_questions(
    session: AsyncSession, user: User, f: QuestionFilters, limit: int, cursor: str | None
) -> QuestionPage:
    await ensure_track(session, user, f.track)
    offset = _decode_offset(cursor)
    base = apply_filters(select(Question.id), f, user)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))

    order = [Question.year.desc(), Question.id]
    if f.q and f.q.strip():
        order = [func.ts_rank(Question.search_vector, _tsquery(f.q)).desc(), Question.id]
    last = _last_attempt_subquery(user.id)
    stmt = apply_filters(
        select(
            Question,
            KnowledgeArea.code,
            Subject.id,
            Subject.name,
            last.c.is_correct,
            exists()
            .where(QuestionBookmark.user_id == user.id, QuestionBookmark.question_id == Question.id)
            .label("bookmarked"),
        )
        .join(KnowledgeArea, KnowledgeArea.id == Question.area_id)
        .outerjoin(Subject, Subject.id == Question.subject_id)
        .outerjoin(last, last.c.question_id == Question.id),
        f,
        user,
    )
    rows = (await session.execute(stmt.order_by(*order).offset(offset).limit(limit + 1))).all()
    labels = await contest_labels(session, [r[0].id for r in rows[:limit]])
    items = [
        QuestionListItem(
            id=q.id,
            year=q.year,
            track=track_of(code),
            format=q.format,
            contest=labels.get(q.id),
            area_code=code,
            subject=SubjectRef(id=sid, name=sname) if sid else None,
            skill_code=q.skill_code,
            foreign_language=q.foreign_language,
            difficulty=difficulty_of(q.irt_b),
            preview=preview(q.statement_md),
            bookmarked=bookmarked,
            last_attempt_correct=last_correct,
        )
        for q, code, sid, sname, last_correct, bookmarked in rows[:limit]
    ]
    next_cursor = _encode_offset(offset + limit) if len(rows) > limit else None
    return QuestionPage(items=items, next_cursor=next_cursor, total=total or 0)


async def contest_labels(session: AsyncSession, question_ids: list[int]) -> dict[int, str]:
    if not question_ids:
        return {}
    rows = await session.execute(
        select(ContestExamQuestion.question_id, ContestExam)
        .join(ContestExam, ContestExam.id == ContestExamQuestion.contest_exam_id)
        .where(ContestExamQuestion.question_id.in_(question_ids))
    )
    return {qid: f"{e.board} · {e.organization} · {e.position}" for qid, e in rows}


# ---- detalhe --------------------------------------------------------------------


async def _get_question(
    session: AsyncSession, question_id: int, user: User | None = None
) -> Question:
    """Busca a questão. Com `user`, aplica o que o aluno pode ver (publicada, módulo ligado)."""
    q = await session.get(Question, question_id)
    if q is None:
        raise NotFoundError("Questão não encontrada.")
    if user is not None:
        if not q.is_published and user.role != UserRole.admin:
            raise NotFoundError("Questão não encontrada.")
        area = await session.get(KnowledgeArea, q.area_id)
        await ensure_track(session, user, track_of(area.code))
    return q


async def _question_parts(session: AsyncSession, q: Question, storage: LocalStorage, user: User):
    area = await session.get(KnowledgeArea, q.area_id)
    subject = await session.get(Subject, q.subject_id) if q.subject_id else None
    options = (
        await session.scalars(
            select(QuestionOption)
            .where(QuestionOption.question_id == q.id)
            .order_by(QuestionOption.letter)
        )
    ).all()
    topics = (
        await session.scalars(
            select(Topic)
            .join(QuestionTopic, QuestionTopic.topic_id == Topic.id)
            .where(QuestionTopic.question_id == q.id)
        )
    ).all()
    positions = (
        await session.execute(
            select(Exam, ExamQuestion.position)
            .join(ExamQuestion, ExamQuestion.exam_id == Exam.id)
            .where(ExamQuestion.question_id == q.id)
            .order_by(Exam.year, Exam.day, Exam.booklet_color)
        )
    ).all()
    bookmarked = (
        await session.scalar(
            select(QuestionBookmark.question_id).where(
                QuestionBookmark.user_id == user.id, QuestionBookmark.question_id == q.id
            )
        )
        is not None
    )
    contest_positions = (
        await session.execute(
            select(ContestExam, ContestExamQuestion.position)
            .join(ContestExamQuestion, ContestExamQuestion.contest_exam_id == ContestExam.id)
            .where(ContestExamQuestion.question_id == q.id)
        )
    ).all()
    return {
        "id": q.id,
        "year": q.year,
        "track": track_of(area.code),
        "format": q.format,
        "area_code": area.code,
        "area_name": area.name,
        "subject": SubjectRef(id=subject.id, name=subject.name) if subject else None,
        "topics": [
            TopicOut(id=t.id, name=t.name, slug=t.slug, parent_id=t.parent_id) for t in topics
        ],
        "skill_code": q.skill_code,
        "foreign_language": q.foreign_language,
        "difficulty": difficulty_of(q.irt_b),
        "statement_md": render_assets(q.statement_md, storage),
        "options": [
            OptionOut(letter=o.letter, text_md=render_assets(o.text_md, storage)) for o in options
        ],
        "bookmarked": bookmarked,
        "positions": [
            ExamPosition(
                label=f"ENEM {e.year} · {e.day}º dia · caderno {e.booklet_color}", position=pos
            )
            for e, pos in positions
        ]
        + [
            ExamPosition(
                label=f"{e.board} · {e.organization} · {e.position} ({e.year})", position=pos
            )
            for e, pos in contest_positions
        ],
    }


async def get_question(
    session: AsyncSession, storage: LocalStorage, user: User, question_id: int
) -> QuestionOut:
    q = await _get_question(session, question_id, user)
    if q.is_annulled:
        raise NotFoundError("Questão não encontrada.")
    return QuestionOut(**await _question_parts(session, q, storage, user))


# ---- resposta e favoritos -------------------------------------------------------


async def _owned_session(
    session: AsyncSession, user: User, session_id: uuid.UUID
) -> PracticeSession:
    ps = await session.get(PracticeSession, session_id)
    if ps is None or ps.user_id != user.id:
        raise NotFoundError("Sessão de prática não encontrada.")
    return ps


async def answer(session: AsyncSession, user: User, question_id: int, data: AnswerIn) -> AnswerOut:
    q = await _get_question(session, question_id, user)
    if q.is_annulled or q.correct_option is None:
        raise AppError("question_annulled", "Esta questão foi anulada.", 409)
    if q.format == QuestionFormat.true_false and data.selected_option not in ("C", "E"):
        raise AppError("invalid_option", "Responda Certo (C) ou Errado (E).", 422)

    practice: PracticeSession | None = None
    if data.practice_session_id:
        practice = await _owned_session(session, user, data.practice_session_id)
        if practice.finished_at is not None:
            raise AppError("session_finished", "Esta sessão já foi encerrada.", 409)
        if practice.question_ids and question_id not in practice.question_ids:
            raise AppError("question_not_in_session", "A questão não faz parte desta sessão.", 422)

    is_correct = data.selected_option == q.correct_option
    session.add(
        QuestionAttempt(
            user_id=user.id,
            question_id=q.id,
            practice_session_id=practice.id if practice else None,
            selected_option=data.selected_option,
            is_correct=is_correct,
            time_spent_seconds=data.time_spent_seconds,
        )
    )
    await session.commit()

    if practice is not None and practice.mode != PracticeMode.livre:
        return AnswerOut(is_correct=None, correct_option=None, explanation_md=None)
    return AnswerOut(
        is_correct=is_correct, correct_option=q.correct_option, explanation_md=q.explanation_md
    )


async def set_bookmark(session: AsyncSession, user: User, question_id: int, on: bool) -> None:
    await _get_question(session, question_id, user)
    if on:
        await session.execute(
            insert(QuestionBookmark)
            .values(user_id=user.id, question_id=question_id)
            .on_conflict_do_nothing()
        )
    else:
        await session.execute(
            delete(QuestionBookmark).where(
                QuestionBookmark.user_id == user.id, QuestionBookmark.question_id == question_id
            )
        )
    await session.commit()


# ---- sessões de prática ---------------------------------------------------------


async def _session_answers(session: AsyncSession, ps: PracticeSession) -> dict[int, str]:
    """Última alternativa escolhida para cada questão da sessão."""
    rows = (
        await session.execute(
            select(QuestionAttempt.question_id, QuestionAttempt.selected_option)
            .where(QuestionAttempt.practice_session_id == ps.id)
            .ext(distinct_on(QuestionAttempt.question_id))
            .order_by(
                QuestionAttempt.question_id,
                QuestionAttempt.answered_at.desc(),
                QuestionAttempt.id.desc(),
            )
        )
    ).all()
    return {qid: opt for qid, opt in rows if opt}


async def _session_out(session: AsyncSession, ps: PracticeSession) -> PracticeSessionOut:
    return PracticeSessionOut(
        id=ps.id,
        mode=ps.mode,
        filters=QuestionFilters(**(ps.filters or {})),
        question_ids=ps.question_ids or [],
        time_limit_seconds=ps.time_limit_seconds,
        started_at=ps.started_at,
        finished_at=ps.finished_at,
        answers=await _session_answers(session, ps),
    )


async def create_session(
    session: AsyncSession, user: User, data: PracticeSessionIn
) -> PracticeSessionOut:
    await ensure_track(session, user, data.filters.track)
    stmt = apply_filters(select(Question.id), data.filters, user).order_by(func.random())
    ids = list((await session.scalars(stmt.limit(data.size))).all())
    if not ids:
        raise AppError("no_questions", "Nenhuma questão encontrada com esses filtros.", 422)
    if data.mode == PracticeMode.livre and data.time_limit_seconds:
        raise AppError("invalid_time_limit", "A prática livre não tem cronômetro.", 422)
    ps = PracticeSession(
        user_id=user.id,
        mode=data.mode,
        filters=data.filters.model_dump(exclude_none=True, mode="json"),
        question_ids=ids,
        time_limit_seconds=data.time_limit_seconds,
    )
    session.add(ps)
    await session.commit()
    await session.refresh(ps)
    return await _session_out(session, ps)


async def get_session(
    session: AsyncSession, user: User, session_id: uuid.UUID
) -> PracticeSessionOut:
    return await _session_out(session, await _owned_session(session, user, session_id))


async def finish_session(session: AsyncSession, user: User, session_id: uuid.UUID) -> SessionResult:
    ps = await _owned_session(session, user, session_id)
    if ps.finished_at is None:
        ps.finished_at = utcnow()
        await session.commit()
    answers = await _session_answers(session, ps)
    ids = ps.question_ids or []
    rows = (
        await session.execute(
            select(Question.id, Question.correct_option, KnowledgeArea.code, KnowledgeArea.name)
            .join(KnowledgeArea, KnowledgeArea.id == Question.area_id)
            .where(Question.id.in_(ids))
        )
    ).all()
    info = {qid: (opt, code, name) for qid, opt, code, name in rows}
    items: list[SessionItemResult] = []
    areas: dict[str, list] = {}
    for qid in ids:
        correct_opt, code, name = info.get(qid, (None, "?", "?"))
        selected = answers.get(qid)
        ok = selected is not None and selected == correct_opt
        items.append(
            SessionItemResult(
                question_id=qid, selected_option=selected, correct_option=correct_opt, is_correct=ok
            )
        )
        bucket = areas.setdefault(code, [name, 0, 0])
        if selected is not None:
            bucket[1] += 1
            bucket[2] += int(ok)
    correct = sum(i.is_correct for i in items)
    return SessionResult(
        session=await _session_out(session, ps),
        total=len(ids),
        answered=len(answers),
        correct=correct,
        by_area=[
            AreaScore(
                code=c, name=n, answered=a, correct=k, pct=round(100 * k / a, 1) if a else None
            )
            for c, (n, a, k) in sorted(areas.items())
        ],
        items=items,
    )


# ---- estatísticas ---------------------------------------------------------------


def _pct(correct: int, answered: int) -> float | None:
    return round(100 * correct / answered, 1) if answered else None


async def stats(session: AsyncSession, user: User, weeks: int = 12) -> QuestionStatsOut:
    last = _last_attempt_subquery(user.id)
    base = select(last.c.question_id, last.c.is_correct).subquery("l")
    joined = (
        select(base.c.question_id, base.c.is_correct, Question.area_id, Question.subject_id)
        .join(Question, Question.id == base.c.question_id)
        .subquery("lq")
    )

    area_rows = (
        await session.execute(
            select(
                KnowledgeArea.code,
                KnowledgeArea.name,
                func.count(joined.c.question_id),
                func.count().filter(joined.c.is_correct),
            )
            .select_from(KnowledgeArea)
            .outerjoin(joined, joined.c.area_id == KnowledgeArea.id)
            .group_by(KnowledgeArea.id)
            .order_by(KnowledgeArea.id)
        )
    ).all()
    by_area = [
        AreaScore(code=c, name=n, answered=a, correct=k, pct=_pct(k, a)) for c, n, a, k in area_rows
    ]

    subject_rows = (
        await session.execute(
            select(Subject.id, Subject.name, func.count(), func.count().filter(joined.c.is_correct))
            .join(joined, joined.c.subject_id == Subject.id)
            .group_by(Subject.id)
            .order_by(Subject.name)
        )
    ).all()
    topic_rows = (
        await session.execute(
            select(Topic.id, Topic.name, func.count(), func.count().filter(joined.c.is_correct))
            .join(QuestionTopic, QuestionTopic.topic_id == Topic.id)
            .join(joined, joined.c.question_id == QuestionTopic.question_id)
            .group_by(Topic.id)
            .order_by(Topic.name)
        )
    ).all()

    since = utcnow() - timedelta(weeks=weeks)
    week = func.date_trunc("week", QuestionAttempt.answered_at)
    timeline_rows = (
        await session.execute(
            select(week, func.count(), func.count().filter(QuestionAttempt.is_correct))
            .where(QuestionAttempt.user_id == user.id, QuestionAttempt.answered_at >= since)
            .group_by(week)
            .order_by(week)
        )
    ).all()

    answered = sum(a.answered for a in by_area)
    correct = sum(a.correct for a in by_area)
    return QuestionStatsOut(
        answered=answered,
        correct=correct,
        pct=_pct(correct, answered),
        by_area=by_area,
        by_subject=[
            GroupScore(id=i, name=n, answered=a, correct=k, pct=_pct(k, a))
            for i, n, a, k in subject_rows
        ],
        by_topic=[
            GroupScore(id=i, name=n, answered=a, correct=k, pct=_pct(k, a))
            for i, n, a, k in topic_rows
        ],
        timeline=[TimelinePoint(week=w.date(), answered=a, correct=k) for w, a, k in timeline_rows],
    )


# ---- admin ----------------------------------------------------------------------


async def admin_list(
    session: AsyncSession, reviewed: bool | None, limit: int, cursor: str | None
) -> tuple[list[Question], str | None, int]:
    offset = _decode_offset(cursor)
    stmt = select(Question)
    if reviewed is not None:
        stmt = stmt.where(Question.reviewed.is_(reviewed))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = (
        await session.scalars(
            stmt.order_by(Question.year.desc(), Question.id).offset(offset).limit(limit + 1)
        )
    ).all()
    nxt = _encode_offset(offset + limit) if len(rows) > limit else None
    return list(rows[:limit]), nxt, total or 0


async def admin_get(
    session: AsyncSession, storage: LocalStorage, user: User, question_id: int
) -> AdminQuestionOut:
    q = await _get_question(session, question_id)
    parts = await _question_parts(session, q, storage, user)
    return AdminQuestionOut(
        **parts,
        correct_option=q.correct_option,
        explanation_md=q.explanation_md,
        is_annulled=q.is_annulled,
        reviewed=q.reviewed,
        inep_item_code=q.inep_item_code,
        irt_a=float(q.irt_a) if q.irt_a is not None else None,
        irt_b=float(q.irt_b) if q.irt_b is not None else None,
        irt_c=float(q.irt_c) if q.irt_c is not None else None,
        source=q.source,
        is_published=q.is_published,
    )


NULLABLE_FIELDS = {"explanation_md", "subject_id", "correct_option"}


async def admin_update(session: AsyncSession, question_id: int, data: AdminQuestionUpdate) -> None:
    q = await _get_question(session, question_id)
    fields = data.model_dump(exclude_unset=True)
    if "subject_id" in fields and fields["subject_id"] is not None:
        subject = await session.get(Subject, fields["subject_id"])
        if subject is None or subject.area_id != q.area_id:
            raise AppError("invalid_subject", "Disciplina inválida para a área da questão.", 422)
    for key in (
        "statement_md",
        "explanation_md",
        "subject_id",
        "correct_option",
        "is_annulled",
        "reviewed",
        "format",
    ):
        if key in fields and (fields[key] is not None or key in NULLABLE_FIELDS):
            setattr(q, key, fields[key])
    if q.format == QuestionFormat.true_false and q.correct_option not in (None, "C", "E"):
        raise AppError("invalid_answer", "Questão Certo/Errado: o gabarito é C ou E.", 422)
    if q.is_published and not q.is_annulled and q.correct_option is None:
        raise AppError("answer_required", "Questão não anulada precisa de gabarito.", 422)
    if data.topic_ids is not None:
        await session.execute(delete(QuestionTopic).where(QuestionTopic.question_id == q.id))
        for tid in set(data.topic_ids):
            topic = await session.get(Topic, tid)
            if topic is None or (q.subject_id and topic.subject_id != q.subject_id):
                raise AppError("invalid_topic", f"Tópico {tid} inválido para a disciplina.", 422)
            session.add(QuestionTopic(question_id=q.id, topic_id=tid))
    if data.options is not None:
        await session.execute(delete(QuestionOption).where(QuestionOption.question_id == q.id))
        for opt in data.options:
            session.add(QuestionOption(question_id=q.id, letter=opt.letter, text_md=opt.text_md))
    await session.commit()


def asset_keys(md: str) -> list[str]:
    return ASSET_RE.findall(md)
