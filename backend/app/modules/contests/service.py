"""Provas de concurso: importação (PDF → questões), revisão, figuras e publicação."""

import asyncio
import io
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime

from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import estimate_cost, pricing_table
from app.ai.config import task_settings
from app.core.enums import ContestExamStatus, QuestionFormat
from app.core.errors import AppError, NotFoundError
from app.jobs.queue import enqueue
from app.modules.contests import extraction
from app.modules.contests.models import ContestExam, ContestExamQuestion
from app.modules.contests.schemas import (
    ContestExamDetail,
    ContestExamOut,
    ContestFiltersOut,
    ContestMetaIn,
    ContestQuestionOut,
    EstimateOut,
    FigureIn,
)
from app.modules.questions.models import (
    KnowledgeArea,
    Question,
    QuestionAsset,
    QuestionOption,
    Subject,
)
from app.modules.questions.service import CONTEST_AREA, preview
from app.modules.system.budget import budget_status, ensure_budget
from app.modules.system.settings import get_setting, log_event
from app.modules.users.models import User
from app.storage import LocalStorage

MAX_PDF_BYTES = 40 * 1024 * 1024
FIGURE_RE = re.compile(r"\[Figura:[^\]]*\]")


def exam_prefix(exam_id: int) -> str:
    return f"contests/{exam_id}/"


def page_key(exam_id: int, page: int) -> str:
    return f"{exam_prefix(exam_id)}pages/p{page:03d}.jpg"


def _check_pdf(data: bytes, label: str) -> int:
    if not data:
        raise AppError("pdf_required", f"Envie o PDF {label}.", 422)
    if len(data) > MAX_PDF_BYTES:
        raise AppError("pdf_too_large", f"O PDF {label} passa de 40 MB.", 422)
    if not data.startswith(b"%PDF"):
        raise AppError("invalid_pdf", f"O arquivo {label} não é um PDF.", 422)
    try:
        pages = extraction.page_count(data)
    except extraction.PdfError as exc:
        raise AppError("invalid_pdf", str(exc), 422) from exc
    if pages > extraction.MAX_PAGES:
        raise AppError(
            "pdf_too_long",
            f"O PDF {label} tem {pages} páginas (máximo {extraction.MAX_PAGES}).",
            422,
        )
    return pages


async def estimate(session: AsyncSession, data: bytes) -> EstimateOut:
    pages = _check_pdf(data, "da prova")
    cfg = await task_settings(session, "contest_extraction")
    n_chunks = len(extraction.chunks(pages))
    billed_pages = pages + n_chunks  # cada trecho repete uma página
    table = pricing_table(await get_setting(session, "ai_pricing"))
    cost = estimate_cost(
        table,
        cfg["model"],
        billed_pages * extraction.EST_INPUT_TOKENS_PER_PAGE,
        pages * extraction.EST_OUTPUT_TOKENS_PER_PAGE,
        0,
        0,
    )
    status = await budget_status(session)
    left = round(status.budget_usd - status.spent_usd, 2) if status.budget_usd else None
    return EstimateOut(
        pages=pages,
        chunks=n_chunks,
        provider=cfg["provider"],
        model=cfg["model"],
        estimated_cost_usd=float(cost) if cost is not None else None,
        budget_left_usd=left,
        budget_exceeded=status.exceeded,
    )


async def create(
    session: AsyncSession,
    storage: LocalStorage,
    admin: User,
    meta: ContestMetaIn,
    exam_pdf: bytes,
    answer_key_pdf: bytes | None,
) -> ContestExam:
    await ensure_budget(session)  # importação também para quando o orçamento acaba
    pages = _check_pdf(exam_pdf, "da prova")
    if answer_key_pdf:
        _check_pdf(answer_key_pdf, "do gabarito")
    exam = ContestExam(
        **meta.model_dump(),
        exam_key="",
        page_count=pages,
        created_by=admin.id,
    )
    session.add(exam)
    await session.flush()
    exam.exam_key = f"{exam_prefix(exam.id)}prova.pdf"
    await storage.put(exam.exam_key, exam_pdf, "application/pdf")
    if answer_key_pdf:
        exam.answer_key_key = f"{exam_prefix(exam.id)}gabarito.pdf"
        await storage.put(exam.answer_key_key, answer_key_pdf, "application/pdf")
    await enqueue(session, "contest.extract", {"contest_exam_id": exam.id}, max_attempts=3)
    log_event(
        session, "contest", f"Prova importada: {meta.board} · {meta.organization} ({meta.year})"
    )
    await session.commit()
    return exam


# ---- junção prova + gabarito -----------------------------------------------------


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\(concursos\)", "", text)
    return " ".join(re.sub(r"[^a-z ]", " ", text).split())


def match_subject(suggestion: str | None, subjects: dict[str, int]) -> int | None:
    """Disciplina sugerida pela IA → id, por nome sem acento (exato, depois contido)."""
    if not suggestion:
        return None
    target = _norm(suggestion)
    if target in subjects:
        return subjects[target]
    aliases = {
        "portugues": "lingua portuguesa",
        "ingles": "lingua inglesa",
        "rlm": "raciocinio logico",
    }
    target = aliases.get(target, target)
    for name, sid in subjects.items():
        if target == name or target in name or name in target:
            return sid
    return None


async def contest_subjects(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        select(Subject.name, Subject.id)
        .join(KnowledgeArea, KnowledgeArea.id == Subject.area_id)
        .where(KnowledgeArea.code == CONTEST_AREA)
    )
    return {_norm(name): sid for name, sid in rows}


async def contest_subject_names(session: AsyncSession) -> list[str]:
    rows = await session.scalars(
        select(Subject.name)
        .join(KnowledgeArea, KnowledgeArea.id == Subject.area_id)
        .where(KnowledgeArea.code == CONTEST_AREA)
        .order_by(Subject.name)
    )
    return list(rows)


async def save_extraction(
    session: AsyncSession,
    exam: ContestExam,
    found: extraction.Extraction,
    answers: dict[int, str] | None,
) -> int:
    """Grava as questões extraídas (não publicadas) com os avisos para a revisão."""
    area_id = await session.scalar(
        select(KnowledgeArea.id).where(KnowledgeArea.code == CONTEST_AREA)
    )
    subjects = await contest_subjects(session)
    await _delete_exam_questions(session, exam.id)
    for position, number in enumerate(sorted(found.questions), start=1):
        q = found.questions[number]
        fmt = QuestionFormat(q.formato)
        letters = {a.letra for a in q.alternativas}
        warnings: list[str] = []
        answer = (answers or {}).get(number)
        correct: str | None = None
        annulled = answer == "X"
        if answers is None:
            warnings.append("Sem gabarito: informe a resposta.")
        elif answer is None:
            warnings.append("Questão não encontrada no gabarito: informe a resposta.")
        elif not annulled:
            valid = {"C", "E"} if fmt == QuestionFormat.true_false else letters
            if answer in valid:
                correct = answer
            else:
                warnings.append(f"O gabarito diz {answer}, que não existe nesta questão: confira.")
        if q.tem_figura:
            warnings.append(f"Tem figura na página {q.pagina}: recorte a imagem.")
        subject_id = match_subject(q.disciplina_sugerida, subjects)
        if subject_id is None:
            warnings.append(
                f"Disciplina não identificada ({q.disciplina_sugerida or 'sem sugestão'})."
            )
        question = Question(
            year=exam.year,
            area_id=area_id,
            subject_id=subject_id,
            statement_md=q.enunciado.strip(),
            correct_option=correct,
            is_annulled=annulled,
            source="concurso",
            format=fmt,
            reviewed=False,
            is_published=False,
        )
        session.add(question)
        await session.flush()
        for alt in q.alternativas:
            session.add(
                QuestionOption(question_id=question.id, letter=alt.letra, text_md=alt.texto)
            )
        session.add(
            ContestExamQuestion(
                contest_exam_id=exam.id,
                question_id=question.id,
                position=number if number < 32767 else position,
                page=q.pagina,
                warnings=warnings,
            )
        )
    return len(found.questions)


# ---- consulta --------------------------------------------------------------------


async def _counts(session: AsyncSession, exam_ids: list[int]) -> dict[int, tuple[int, int]]:
    """Questões e questões com aviso pendente, por prova."""
    if not exam_ids:
        return {}
    rows = await session.execute(
        select(ContestExamQuestion.contest_exam_id, ContestExamQuestion.warnings, Question)
        .join(Question, Question.id == ContestExamQuestion.question_id)
        .where(ContestExamQuestion.contest_exam_id.in_(exam_ids))
    )
    out: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for exam_id, warnings, q in rows:
        out[exam_id][0] += 1
        out[exam_id][1] += bool(live_warnings(warnings, q))
    return {k: (v[0], v[1]) for k, v in out.items()}


def exam_out(exam: ContestExam, counts: tuple[int, int] = (0, 0)) -> dict:
    return {
        "id": exam.id,
        "board": exam.board,
        "organization": exam.organization,
        "position": exam.position,
        "level": exam.level,
        "year": exam.year,
        "booklet": exam.booklet,
        "status": exam.status,
        "page_count": exam.page_count,
        "error": exam.error,
        "has_answer_key": exam.answer_key_key is not None,
        "questions": counts[0],
        "warnings": counts[1],
        "created_at": exam.created_at,
        "published_at": exam.published_at,
    }


async def list_exams(session: AsyncSession) -> list[ContestExamOut]:
    exams = (await session.scalars(select(ContestExam).order_by(ContestExam.id.desc()))).all()
    counts = await _counts(session, [e.id for e in exams])
    return [ContestExamOut(**exam_out(e, counts.get(e.id, (0, 0)))) for e in exams]


async def _get(session: AsyncSession, exam_id: int, lock: bool = False) -> ContestExam:
    exam = await session.get(ContestExam, exam_id, with_for_update=lock)
    if exam is None:
        raise NotFoundError("Prova não encontrada.")
    return exam


async def detail(session: AsyncSession, storage: LocalStorage, exam_id: int) -> ContestExamDetail:
    exam = await _get(session, exam_id)
    rows = (
        await session.execute(
            select(ContestExamQuestion, Question, Subject.name)
            .join(Question, Question.id == ContestExamQuestion.question_id)
            .outerjoin(Subject, Subject.id == Question.subject_id)
            .where(ContestExamQuestion.contest_exam_id == exam_id)
            .order_by(ContestExamQuestion.position)
        )
    ).all()
    ids = [q.id for _, q, _ in rows]
    n_options = (
        dict(
            (
                await session.execute(
                    select(QuestionOption.question_id, func.count())
                    .where(QuestionOption.question_id.in_(ids))
                    .group_by(QuestionOption.question_id)
                )
            ).all()
        )
        if ids
        else {}
    )
    n_assets = (
        dict(
            (
                await session.execute(
                    select(QuestionAsset.question_id, func.count())
                    .where(QuestionAsset.question_id.in_(ids))
                    .group_by(QuestionAsset.question_id)
                )
            ).all()
        )
        if ids
        else {}
    )
    questions = [
        ContestQuestionOut(
            id=q.id,
            position=link.position,
            page=link.page,
            format=q.format,
            preview=preview(q.statement_md, 260),
            subject_id=q.subject_id,
            subject_name=subject_name,
            correct_option=q.correct_option,
            is_annulled=q.is_annulled,
            options=n_options.get(q.id, 0),
            assets=n_assets.get(q.id, 0),
            warnings=live_warnings(link.warnings, q),
        )
        for link, q, subject_name in rows
    ]
    pages = exam.page_count or 0 if exam.status != ContestExamStatus.processing else 0
    return ContestExamDetail(
        **exam_out(exam, (len(questions), sum(1 for q in questions if q.warnings))),
        questions_list=questions,
        page_urls=[storage.signed_url(page_key(exam.id, p), 6 * 3600) for p in range(1, pages + 1)],
    )


# ---- ações da revisão ------------------------------------------------------------


async def update_meta(session: AsyncSession, exam_id: int, meta: ContestMetaIn) -> None:
    exam = await _get(session, exam_id, lock=True)
    for key, value in meta.model_dump().items():
        setattr(exam, key, value)
    linked = select(ContestExamQuestion.question_id).where(
        ContestExamQuestion.contest_exam_id == exam_id
    )
    for q in await session.scalars(select(Question).where(Question.id.in_(linked))):
        q.year = meta.year
    await session.commit()


def live_warnings(warnings: list[str], q: Question) -> list[str]:
    """Avisos da importação que ainda valem depois das edições na questão."""
    keep = []
    for w in warnings or []:
        if ("gabarito" in w or "resposta" in w) and (q.correct_option or q.is_annulled):
            continue
        if w.startswith("Disciplina") and q.subject_id:
            continue
        if w.startswith("Tem figura") and not FIGURE_RE.search(q.statement_md):
            continue
        keep.append(w)
    return keep


async def add_figure(
    session: AsyncSession, storage: LocalStorage, exam_id: int, question_id: int, data: FigureIn
) -> None:
    exam = await _get(session, exam_id)
    link = await session.get(ContestExamQuestion, (exam_id, question_id))
    if link is None:
        raise NotFoundError("Questão não pertence a esta prova.")
    if data.page > (exam.page_count or 0):
        raise AppError("invalid_page", "Página inexistente.", 422)
    raw = await storage.get(page_key(exam_id, data.page))

    def crop() -> bytes:
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        box = (
            int(data.x * w),
            int(data.y * h),
            int(min(data.x + data.width, 1) * w),
            int(min(data.y + data.height, 1) * h),
        )
        if box[2] - box[0] < 10 or box[3] - box[1] < 10:
            raise AppError("figure_too_small", "Selecione uma área maior.", 422)
        buf = io.BytesIO()
        img.crop(box).save(buf, "JPEG", quality=90)
        return buf.getvalue()

    image = await asyncio.to_thread(crop)
    q = await session.get(Question, question_id, with_for_update=True)
    position = (
        await session.scalar(
            select(func.coalesce(func.max(QuestionAsset.position), 0)).where(
                QuestionAsset.question_id == question_id
            )
        )
    ) + 1
    key = f"questions/concursos/{exam_id}/{question_id}-{position}.jpg"
    await storage.put(key, image, "image/jpeg")
    session.add(
        QuestionAsset(
            question_id=question_id, storage_key=key, alt_text=data.alt, position=position
        )
    )
    markdown = f"![{data.alt}](asset:{key})"
    if FIGURE_RE.search(q.statement_md):
        q.statement_md = FIGURE_RE.sub(lambda _: markdown, q.statement_md, count=1)
    else:
        q.statement_md = f"{q.statement_md.rstrip()}\n\n{markdown}"
    await session.commit()


async def publish(session: AsyncSession, exam_id: int) -> None:
    exam = await _get(session, exam_id, lock=True)
    if exam.status not in (ContestExamStatus.review, ContestExamStatus.published):
        raise AppError("not_ready", "A prova ainda não terminou de ser importada.", 409)
    linked = select(ContestExamQuestion.question_id).where(
        ContestExamQuestion.contest_exam_id == exam_id
    )
    questions = (await session.scalars(select(Question).where(Question.id.in_(linked)))).all()
    if not questions:
        raise AppError("no_questions", "A prova não tem questões para publicar.", 409)
    missing = [q.id for q in questions if not q.is_annulled and not q.correct_option]
    if missing:
        raise AppError(
            "missing_answers",
            f"{len(missing)} questão(ões) sem gabarito. Informe a resposta ou marque como anulada.",
            409,
            details={"question_ids": missing},
        )
    for q in questions:
        q.is_published = True
        q.reviewed = True
    exam.status = ContestExamStatus.published
    exam.published_at = datetime.now(UTC)
    log_event(
        session, "contest", f"Prova publicada: {exam.board} · {exam.organization} ({exam.year})"
    )
    await session.commit()


async def unpublish(session: AsyncSession, exam_id: int) -> None:
    exam = await _get(session, exam_id, lock=True)
    if exam.status != ContestExamStatus.published:
        return
    linked = select(ContestExamQuestion.question_id).where(
        ContestExamQuestion.contest_exam_id == exam_id
    )
    for q in await session.scalars(select(Question).where(Question.id.in_(linked))):
        q.is_published = False
    exam.status = ContestExamStatus.review
    exam.published_at = None
    log_event(session, "contest", f"Prova despublicada: {exam.board} · {exam.organization}")
    await session.commit()


async def retry(session: AsyncSession, exam_id: int) -> None:
    exam = await _get(session, exam_id, lock=True)
    if exam.status != ContestExamStatus.failed:
        raise AppError("not_failed", "Só dá para reimportar provas que falharam.", 409)
    await ensure_budget(session)
    exam.status = ContestExamStatus.processing
    exam.error = None
    await enqueue(session, "contest.extract", {"contest_exam_id": exam.id}, max_attempts=3)
    await session.commit()


async def _delete_exam_questions(session: AsyncSession, exam_id: int) -> None:
    linked = select(ContestExamQuestion.question_id).where(
        ContestExamQuestion.contest_exam_id == exam_id
    )
    await session.execute(delete(Question).where(Question.id.in_(linked)))


async def remove(session: AsyncSession, storage: LocalStorage, exam_id: int) -> None:
    exam = await _get(session, exam_id, lock=True)
    await _delete_exam_questions(session, exam_id)
    label = f"{exam.board} · {exam.organization} ({exam.year})"
    await session.delete(exam)
    log_event(session, "contest", f"Prova excluída: {label}")
    await session.commit()
    await storage.delete_prefix(exam_prefix(exam_id))
    await storage.delete_prefix(f"questions/concursos/{exam_id}/")


async def create_subject(session: AsyncSession, name: str) -> int:
    area_id = await session.scalar(
        select(KnowledgeArea.id).where(KnowledgeArea.code == CONTEST_AREA)
    )
    slug = "cp-" + "-".join(_norm(name).split())
    if await session.scalar(select(Subject.id).where(Subject.slug == slug)):
        raise AppError("subject_exists", "Essa disciplina já existe.", 409)
    subject = Subject(area_id=area_id, name=name.strip(), slug=slug)
    session.add(subject)
    await session.commit()
    return subject.id


# ---- filtros do aluno ------------------------------------------------------------


async def public_filters(session: AsyncSession) -> ContestFiltersOut:
    exams = (
        await session.scalars(
            select(ContestExam)
            .where(ContestExam.status == ContestExamStatus.published)
            .order_by(ContestExam.year.desc(), ContestExam.board)
        )
    ).all()
    values: dict[str, set] = defaultdict(set)
    for e in exams:
        values["boards"].add(e.board)
        values["organizations"].add(e.organization)
        values["positions"].add(e.position)
        values["years"].add(e.year)
        if e.level:
            values["levels"].add(e.level)
    return ContestFiltersOut(
        boards=sorted(values["boards"]),
        organizations=sorted(values["organizations"]),
        positions=sorted(values["positions"]),
        years=sorted(values["years"], reverse=True),
        levels=sorted(values["levels"]),
        exams=[
            {"id": e.id, "label": f"{e.board} · {e.organization} · {e.position} ({e.year})"}
            for e in exams
        ],
    )
