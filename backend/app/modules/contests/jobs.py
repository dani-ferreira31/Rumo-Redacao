"""Job `contest.extract`: PDF da prova (+ gabarito) → questões em revisão."""

import asyncio
import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIError, save_usage
from app.ai.config import resolve_task
from app.core.enums import ContestExamStatus
from app.core.logging import bind_log_context
from app.jobs.models import Job
from app.jobs.registry import job_handler
from app.modules.contests import extraction
from app.modules.contests.models import ContestExam
from app.modules.contests.service import contest_subject_names, page_key, save_extraction
from app.storage import get_storage

logger = logging.getLogger(__name__)

FAILED = "Não consegui ler a prova com a IA. Veja o motivo abaixo e tente de novo."


async def _fail(session: AsyncSession, exam_id: int, message: str, exc: Exception | None) -> None:
    await session.rollback()
    if isinstance(exc, AIError) and exc.usage:
        await save_usage(session, exc.usage)
    await session.execute(
        update(ContestExam)
        .where(ContestExam.id == exam_id)
        .values(status=ContestExamStatus.failed, error=message[:1000])
    )
    await session.commit()


@job_handler("contest.extract")
async def extract_contest(session: AsyncSession, payload: dict[str, Any], job: Job) -> None:
    exam_id = int(payload["contest_exam_id"])
    bind_log_context(contest_exam_id=exam_id)
    exam = await session.get(ContestExam, exam_id, with_for_update=True)
    if exam is None or exam.status != ContestExamStatus.processing:
        return
    try:
        await _do_extract(session, exam)
    except (AIError, extraction.PdfError) as exc:
        logger.warning("contest_extract_failed", extra={"extra_fields": {"error": str(exc)}})
        await _fail(session, exam_id, f"{FAILED} ({exc})", exc)
    except Exception as exc:
        if job.attempts >= job.max_attempts:
            await _fail(session, exam_id, f"{FAILED} ({type(exc).__name__})", exc)
        raise


async def _do_extract(session: AsyncSession, exam: ContestExam) -> None:
    storage = get_storage()
    exam_pdf = await storage.get(exam.exam_key)

    images = await asyncio.to_thread(extraction.render_pages, exam_pdf)
    for number, image in enumerate(images, start=1):
        await storage.put(page_key(exam.id, number), image, "image/jpeg")
    exam.page_count = len(images)

    meta = extraction.ExamMeta(
        board=exam.board,
        organization=exam.organization,
        position=exam.position,
        year=exam.year,
        booklet=exam.booklet,
        subjects=await contest_subject_names(session),
    )
    config = await resolve_task(session, "contest_extraction")
    found = await extraction.extract_questions(exam_pdf, meta, config, exam.id)
    results = list(found.results)

    answers: dict[int, str] | None = None
    if exam.answer_key_key and found.questions:
        key_pdf = await storage.get(exam.answer_key_key)
        key = await extraction.read_answer_key(
            key_pdf, meta, sorted(found.questions), config, exam.id
        )
        results.append(key)
        answers = {r.numero: r.resposta for r in key.output.respostas}

    await save_extraction(session, exam, found, answers)
    for result in results:
        await save_usage(session, result)
    exam.status = ContestExamStatus.review
    exam.error = None if found.questions else "Nenhuma questão encontrada no PDF."
    await session.commit()
