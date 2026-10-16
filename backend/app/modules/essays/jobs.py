"""Jobs do pipeline de redação: essay.transcribe e essay.grade (rodam no worker)."""

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIError, save_usage
from app.ai.config import resolve_task
from app.ai.grading import GradingInput, grade_once, prompt_version
from app.ai.transcription import transcribe, transcription_to_text
from app.core.config import get_settings
from app.core.enums import EssayStatus, EssayZeroReason
from app.core.logging import bind_log_context
from app.core.security import utcnow
from app.email.service import queue_email
from app.jobs.models import Job
from app.jobs.registry import job_handler
from app.modules.essays import imaging
from app.modules.essays.checks import CheckResult, run_checks
from app.modules.essays.consolidation import (
    consolidate,
    feedback_from,
    is_discrepant,
    normalize_run,
)
from app.modules.essays.models import (
    Essay,
    EssayGradingRun,
    EssayImage,
    EssayResult,
    EssayTheme,
)
from app.modules.users.models import User
from app.storage import get_storage

logger = logging.getLogger(__name__)

TRANSCRIBE_FAILED = (
    "Não conseguimos transcrever a foto. Tente de novo ou envie uma foto mais nítida."
)
GRADE_FAILED = "Não conseguimos concluir a correção agora. Tente de novo em alguns minutos."

PRE_AI_ZERO_MESSAGES = {
    EssayZeroReason.folha_em_branco: (
        "A redação foi considerada em branco. No ENEM, a folha sem texto recebe nota zero."
    ),
    EssayZeroReason.texto_insuficiente: (
        "A redação tem {lines} linha(s) de texto. No ENEM, textos com até 7 linhas recebem nota "
        "zero (texto insuficiente). Escreva pelo menos 8 linhas; o ideal é ocupar entre 25 e 30."
    ),
    EssayZeroReason.copia_textos_motivadores: (
        "Descontadas as linhas com trechos copiados dos textos motivadores, sobraram {own} "
        "linha(s) "
        "de texto próprio. No ENEM, isso configura texto insuficiente e a redação recebe nota zero."
    ),
}


async def _load_essay(session: AsyncSession, payload: dict[str, Any]) -> Essay | None:
    essay_id = uuid.UUID(payload["essay_id"])
    bind_log_context(essay_id=str(essay_id))
    return await session.get(Essay, essay_id, with_for_update=True)


async def _fail(
    session: AsyncSession, essay_id: uuid.UUID, message: str, exc: Exception | None = None
) -> None:
    await session.rollback()
    if isinstance(exc, AIError) and exc.usage:
        await save_usage(session, exc.usage)  # o que já foi cobrado entra no custo
    await session.execute(
        update(Essay)
        .where(Essay.id == essay_id)
        .values(status=EssayStatus.failed, error_message=message)
    )
    await session.commit()


def _is_last_attempt(job: Job) -> bool:
    return job.attempts >= job.max_attempts


# ---- ETAPA 1 --------------------------------------------------------------------


@job_handler("essay.transcribe")
async def transcribe_essay(session: AsyncSession, payload: dict[str, Any], job: Job) -> None:
    essay = await _load_essay(session, payload)
    if essay is None or essay.status not in (EssayStatus.uploaded, EssayStatus.transcribing):
        return
    essay_id = essay.id
    essay.status = EssayStatus.transcribing
    await session.commit()  # a tela passa a mostrar "transcrevendo"

    try:
        await _do_transcribe(session, essay_id)
    except (AIError, imaging.InvalidImageError) as exc:
        # não adianta repetir: registra e encerra o job
        logger.warning("essay_transcribe_failed", extra={"extra_fields": {"error": str(exc)}})
        await _fail(session, essay_id, TRANSCRIBE_FAILED, exc)
    except Exception:
        if _is_last_attempt(job):
            await _fail(session, essay_id, TRANSCRIBE_FAILED)
        raise


async def _do_transcribe(session: AsyncSession, essay_id: uuid.UUID) -> None:
    storage = get_storage()
    settings = get_settings()
    essay = await session.get(Essay, essay_id)
    images = (
        await session.scalars(
            select(EssayImage).where(EssayImage.essay_id == essay_id).order_by(EssayImage.page)
        )
    ).all()
    processed_jpegs = []
    image_info = []
    for img in images:
        original = await storage.get(img.original_storage_key)
        processed = await asyncio.to_thread(
            imaging.preprocess, original, settings.essay_image_max_long_edge
        )
        key = img.original_storage_key.replace("-original.", "-processed.").rsplit(".", 1)[0]
        key = f"{key}.jpg"
        await storage.put(key, processed.data, "image/jpeg")
        img.storage_key = key
        img.width, img.height = processed.width, processed.height
        processed_jpegs.append(processed.data)
        image_info.append(
            {"page": img.page, "cropped": processed.cropped, "deskew": processed.deskew_degrees}
        )

    config = await resolve_task(session, "transcription")
    result, version = await transcribe(
        processed_jpegs, config=config, user_id=essay.user_id, essay_id=essay_id
    )
    await save_usage(session, result)
    output = result.output
    essay.transcription_raw = {
        **output.model_dump(),
        "prompt_version": version,
        "model": result.model,
        "images": image_info,
    }
    essay.transcription_text = transcription_to_text(output)
    essay.line_count = sum(1 for line in output.linhas if line.texto.strip())
    essay.status = EssayStatus.awaiting_review
    await session.commit()


# ---- ETAPAS 2 a 5 ---------------------------------------------------------------


@job_handler("essay.grade")
async def grade_essay(session: AsyncSession, payload: dict[str, Any], job: Job) -> None:
    essay = await _load_essay(session, payload)
    if essay is None or essay.status != EssayStatus.grading:
        return
    essay_id = essay.id
    try:
        await _do_grade(session, essay)
    except AIError as exc:
        logger.warning("essay_grade_failed", extra={"extra_fields": {"error": str(exc)}})
        await _fail(session, essay_id, GRADE_FAILED, exc)
    except Exception:
        if _is_last_attempt(job):
            await _fail(session, essay_id, GRADE_FAILED)
        raise


async def _do_grade(session: AsyncSession, essay: Essay) -> None:
    theme = await session.get(EssayTheme, essay.theme_id) if essay.theme_id else None
    motivating = theme.motivating_texts if theme else None
    text = essay.transcription_text or ""
    checks = run_checks(text, essay.input_type, motivating)
    essay.line_count = checks.line_count

    # Uma tentativa anterior pode ter deixado correções parciais.
    await session.execute(delete(EssayGradingRun).where(EssayGradingRun.essay_id == essay.id))
    await session.execute(delete(EssayResult).where(EssayResult.essay_id == essay.id))

    if checks.annulled:
        _save_pre_ai_annulment(session, essay, checks)
    else:
        await _grade_with_ai(session, essay, theme, text, checks)

    essay.status = EssayStatus.graded
    essay.graded_at = utcnow()
    await _queue_graded_email(session, essay)
    await session.commit()


def _save_pre_ai_annulment(session: AsyncSession, essay: Essay, checks: CheckResult) -> None:
    """Anulações objetivas (em branco, até 7 linhas, cópia): não chamam a IA."""
    message = PRE_AI_ZERO_MESSAGES[checks.zero_reason].format(
        lines=checks.line_count, own=checks.own_line_count
    )
    session.add(
        EssayResult(
            essay_id=essay.id,
            c1=0,
            c2=0,
            c3=0,
            c4=0,
            c5=0,
            annulled=True,
            zero_reason=checks.zero_reason,
            runs_used=0,
            needed_third_run=False,
            feedback={
                "competencies": [],
                "c1_deviations": [],
                "c5_elements": None,
                "general_comment": message,
                "next_steps": [],
                "warnings": checks.warnings,
                "checks": _checks_summary(checks),
            },
        )
    )


def _checks_summary(checks: CheckResult) -> dict[str, Any]:
    return {
        "line_count": checks.line_count,
        "own_line_count": checks.own_line_count,
        "paragraph_count": checks.paragraph_count,
        "word_count": checks.word_count,
        "copied_lines": checks.copied_lines,
        "estimated_lines": checks.estimated_lines,
    }


async def _grade_with_ai(
    session: AsyncSession,
    essay: Essay,
    theme: EssayTheme | None,
    text: str,
    checks: CheckResult,
) -> None:
    data = GradingInput(
        theme_title=theme.title if theme else (essay.custom_theme or ""),
        motivating_texts=theme.motivating_texts if theme else None,
        text=text,
        checks=checks,
    )
    version = prompt_version()
    config = await resolve_task(session, "grading")

    async def one() -> Any:
        return await grade_once(data, config=config, user_id=essay.user_id, essay_id=essay.id)

    # ETAPA 3: duas correções independentes, em paralelo
    results = list(await asyncio.gather(one(), one()))
    runs = [normalize_run(i, r.output) for i, r in enumerate(results, start=1)]

    # ETAPA 4: terceira correção se houver discrepância
    needed_third = is_discrepant(runs[0], runs[1])
    if needed_third:
        third = await one()
        results.append(third)
        runs.append(normalize_run(3, third.output))

    for result, run in zip(results, runs, strict=True):
        await save_usage(session, result)
        session.add(
            EssayGradingRun(
                essay_id=essay.id,
                run_number=run.number,
                model=result.model,
                prompt_version=version,
                c1=run.scores[0],
                c2=run.scores[1],
                c3=run.scores[2],
                c4=run.scores[3],
                c5=run.scores[4],
                annulled=run.annulled,
                zero_reason=run.zero_reason,
                feedback={**result.output.model_dump(), "avisos": run.warnings},
            )
        )

    # ETAPA 5: consolidação
    final = consolidate(runs)
    feedback = feedback_from(final)
    feedback["warnings"] = checks.warnings
    feedback["checks"] = _checks_summary(checks)
    feedback["runs_used"] = final.runs_used
    session.add(
        EssayResult(
            essay_id=essay.id,
            c1=final.scores[0],
            c2=final.scores[1],
            c3=final.scores[2],
            c4=final.scores[3],
            c5=final.scores[4],
            annulled=final.annulled,
            zero_reason=final.zero_reason,
            runs_used=len(runs),
            needed_third_run=needed_third,
            feedback=feedback,
        )
    )
    logger.info(
        "essay_graded",
        extra={
            "extra_fields": {
                "totals": [r.total for r in runs],
                "final": final.total,
                "third_run": needed_third,
            }
        },
    )


async def _queue_graded_email(session: AsyncSession, essay: Essay) -> None:
    user = await session.get(User, essay.user_id)
    if user is None:
        return
    await queue_email(
        session,
        user_id=user.id,
        to=user.email,
        type="essay_graded",
        subject="Sua redação foi corrigida",
        template="essay_graded.html",
        context={"name": user.name, "url": f"{get_settings().app_url}/redacoes/{essay.id}"},
        dedupe_key=f"essay_graded:{essay.id}",
    )
