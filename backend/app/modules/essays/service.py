"""Regras de negócio das redações: envio, revisão, confirmação e consulta."""

import base64
import io
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PIL import Image, UnidentifiedImageError
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.fake import FAKE_MODEL
from app.core.config import get_settings
from app.core.enums import EssayInputType, EssayStatus, UserRole
from app.core.errors import AppError, NotFoundError
from app.core.security import utcnow
from app.jobs.queue import enqueue
from app.modules.essays import imaging  # noqa: F401  (registra o leitor HEIC no Pillow)
from app.modules.essays.checks import find_markers
from app.modules.essays.models import (
    Essay,
    EssayGradingRun,
    EssayImage,
    EssayResult,
    EssayTheme,
)
from app.modules.essays.schemas import (
    C5ElementOut,
    CompetencyOut,
    DeviationOut,
    EssayImageOut,
    EssayOut,
    EssayPage,
    EssaySummary,
    ResultOut,
    StatsOut,
    StatsPoint,
    ThemeOut,
    TranscriptionInfo,
)
from app.modules.system.budget import ensure_budget
from app.modules.system.settings import get_setting
from app.modules.users.models import User
from app.storage import LocalStorage

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_FORMATS = {"JPEG": "jpg", "PNG": "png", "HEIF": "heic", "WEBP": "webp", "MPO": "jpg"}
MAX_PAGES = 2
MAX_TEXT_CHARS = 20000
CUSTOM_THEME_MIN, CUSTOM_THEME_MAX = 5, 300
AI_JOB_MAX_ATTEMPTS = 3


@dataclass
class Upload:
    filename: str
    content_type: str | None
    data: bytes


def essay_prefix(user_id: uuid.UUID, essay_id: uuid.UUID) -> str:
    return f"users/{user_id}/essays/{essay_id}/"


# ---- temas --------------------------------------------------------------------


def theme_out(theme: EssayTheme) -> ThemeOut:
    return ThemeOut(
        id=theme.id,
        title=theme.title,
        year=theme.year,
        is_official=theme.is_official,
        has_motivating_texts=bool(theme.motivating_texts),
    )


async def list_themes(session: AsyncSession, year: int | None) -> list[ThemeOut]:
    stmt = select(EssayTheme).where(EssayTheme.is_official.is_(True))
    if year is not None:
        stmt = stmt.where(EssayTheme.year == year)
    stmt = stmt.order_by(EssayTheme.year.desc().nulls_last(), EssayTheme.title)
    return [theme_out(t) for t in await session.scalars(stmt)]


# ---- envio --------------------------------------------------------------------


def _check_image(upload: Upload) -> str:
    """Valida tamanho e formato real (não confia no content-type). Devolve a extensão."""
    if len(upload.data) == 0:
        raise AppError("invalid_image", f"O arquivo {upload.filename} está vazio.", 422)
    if len(upload.data) > get_settings().essay_max_image_bytes:
        raise AppError("image_too_large", f"A imagem {upload.filename} passa de 10 MB.", 413)
    try:
        with Image.open(io.BytesIO(upload.data)) as img:
            fmt = img.format or ""
            img.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(
            "invalid_image", f"Não foi possível ler {upload.filename} como imagem.", 422
        ) from exc
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise AppError("invalid_image", "Formato não aceito. Envie JPEG, PNG, HEIC ou WebP.", 422)
    return ALLOWED_IMAGE_FORMATS[fmt]


async def _resolve_theme(
    session: AsyncSession, theme_id: uuid.UUID | None, custom_theme: str | None
) -> tuple[EssayTheme | None, str | None]:
    custom = (custom_theme or "").strip() or None
    if bool(theme_id) == bool(custom):
        raise AppError(
            "theme_required", "Escolha um tema oficial ou digite um tema personalizado.", 422
        )
    if theme_id:
        theme = await session.get(EssayTheme, theme_id)
        if theme is None:
            raise AppError("theme_not_found", "Tema não encontrado.", 422)
        return theme, None
    if not CUSTOM_THEME_MIN <= len(custom) <= CUSTOM_THEME_MAX:
        raise AppError(
            "invalid_custom_theme",
            f"O tema deve ter entre {CUSTOM_THEME_MIN} e {CUSTOM_THEME_MAX} caracteres.",
            422,
        )
    return None, custom


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    # no máximo uma linha em branco seguida (separador de parágrafo)
    out: list[str] = []
    for line in lines:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    return "\n".join(out).strip()


async def _check_limits(session: AsyncSession, user: User) -> None:
    """Limite mensal por aluno e orçamento de IA (o admin não tem limite)."""
    if user.role == UserRole.admin:
        return
    limit = (await get_setting(session, "limits")).get("essays_per_month")
    if limit:
        try:
            tz = ZoneInfo(user.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            tz = ZoneInfo("America/Sao_Paulo")
        local = utcnow().astimezone(tz)
        start = datetime(local.year, local.month, 1, tzinfo=tz)
        used = await session.scalar(
            select(func.count())
            .select_from(Essay)
            .where(Essay.user_id == user.id, Essay.created_at >= start)
        )
        if (used or 0) >= int(limit):
            raise AppError(
                "essay_limit_reached",
                f"Você já enviou {limit} redações neste mês, o limite do plano. "
                "No mês que vem o contador zera.",
                429,
                details={"limit": int(limit)},
            )
    await ensure_budget(session, user)


async def create_essay(
    session: AsyncSession,
    storage: LocalStorage,
    user: User,
    *,
    theme_id: uuid.UUID | None,
    custom_theme: str | None,
    images: list[Upload],
    text: str | None,
) -> Essay:
    await _check_limits(session, user)
    theme, custom = await _resolve_theme(session, theme_id, custom_theme)
    text = normalize_text(text) if text else None
    if bool(images) == bool(text):
        raise AppError(
            "content_required",
            "Envie a foto da redação ou digite o texto (apenas um dos dois).",
            422,
        )

    essay = Essay(
        id=uuid.uuid4(),
        user_id=user.id,
        theme_id=theme.id if theme else None,
        custom_theme=custom,
    )

    if text:
        if len(text) > MAX_TEXT_CHARS:
            raise AppError("text_too_long", "O texto está longo demais.", 422)
        essay.input_type = EssayInputType.text
        essay.status = EssayStatus.grading
        essay.transcription_text = text
        essay.confirmed_at = utcnow()
        session.add(essay)
        await session.flush()
        await enqueue(
            session, "essay.grade", {"essay_id": str(essay.id)}, max_attempts=AI_JOB_MAX_ATTEMPTS
        )
        await session.commit()
        return essay

    if len(images) > MAX_PAGES:
        raise AppError("too_many_images", "Envie no máximo 2 fotos (uma por página).", 422)
    extensions = [_check_image(img) for img in images]

    essay.input_type = EssayInputType.photo
    essay.status = EssayStatus.uploaded
    session.add(essay)
    await session.flush()
    prefix = essay_prefix(user.id, essay.id)
    for page, (upload, ext) in enumerate(zip(images, extensions, strict=True), start=1):
        key = f"{prefix}page{page}-original.{ext}"
        await storage.put(key, upload.data, upload.content_type or "application/octet-stream")
        session.add(
            EssayImage(
                essay_id=essay.id,
                page=page,
                original_storage_key=key,
                mime_type=upload.content_type or f"image/{ext}",
            )
        )
    await enqueue(
        session, "essay.transcribe", {"essay_id": str(essay.id)}, max_attempts=AI_JOB_MAX_ATTEMPTS
    )
    await session.commit()
    return essay


# ---- consulta -----------------------------------------------------------------


async def get_owned(session: AsyncSession, user: User, essay_id: uuid.UUID) -> Essay:
    essay = await session.get(Essay, essay_id)
    if essay is None or essay.user_id != user.id:
        raise NotFoundError("Redação não encontrada.")
    return essay


def _theme_title(essay: Essay, theme: EssayTheme | None) -> str:
    if theme is not None:
        return theme.title
    return essay.custom_theme or "Tema removido"


def result_out(result: EssayResult, simulated: bool) -> ResultOut:
    fb = result.feedback or {}
    c5 = fb.get("c5_elements")
    return ResultOut(
        total=result.total,
        scores=[result.c1, result.c2, result.c3, result.c4, result.c5],
        annulled=result.annulled,
        zero_reason=result.zero_reason,
        competencies=[CompetencyOut(**c) for c in fb.get("competencies", [])],
        c1_deviations=[DeviationOut(**d) for d in fb.get("c1_deviations", [])],
        c5_elements={k: C5ElementOut(**v) for k, v in c5.items()} if c5 else None,
        tangent=fb.get("tangent", False),
        human_rights_violation=fb.get("human_rights_violation", False),
        general_comment=fb.get("general_comment", ""),
        next_steps=fb.get("next_steps", []),
        warnings=fb.get("warnings", []),
        needed_third_run=result.needed_third_run,
        simulated=simulated,
    )


async def essay_out(session: AsyncSession, storage: LocalStorage, essay: Essay) -> EssayOut:
    theme = await session.get(EssayTheme, essay.theme_id) if essay.theme_id else None
    images = (
        await session.scalars(
            select(EssayImage).where(EssayImage.essay_id == essay.id).order_by(EssayImage.page)
        )
    ).all()
    raw = essay.transcription_raw or {}
    transcription = None
    if essay.input_type == EssayInputType.photo and raw:
        transcription = TranscriptionInfo(
            title=raw.get("titulo"),
            confidence=raw.get("confianca"),
            observations=raw.get("observacoes"),
            possible_identification=bool(raw.get("possivel_identificacao")),
            illegible_count=int(raw.get("qtd_ilegiveis") or 0),
        )
    result = None
    if essay.status == EssayStatus.graded:
        row = await session.get(EssayResult, essay.id)
        if row is not None:
            simulated = (
                await session.scalar(
                    select(EssayGradingRun.id)
                    .where(
                        EssayGradingRun.essay_id == essay.id, EssayGradingRun.model == FAKE_MODEL
                    )
                    .limit(1)
                )
            ) is not None
            result = result_out(row, simulated)
    return EssayOut(
        id=essay.id,
        status=essay.status,
        input_type=essay.input_type,
        theme=theme_out(theme) if theme else None,
        custom_theme=essay.custom_theme,
        theme_title=_theme_title(essay, theme),
        transcription_text=essay.transcription_text,
        transcription=transcription,
        line_count=essay.line_count,
        images=[
            EssayImageOut(
                page=img.page,
                url=storage.signed_url(img.storage_key) if img.storage_key else None,
                original_url=storage.signed_url(img.original_storage_key),
            )
            for img in images
        ],
        error_message=essay.error_message,
        created_at=essay.created_at,
        confirmed_at=essay.confirmed_at,
        graded_at=essay.graded_at,
        result=result,
    )


def _encode_cursor(created_at: datetime, essay_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(essay_id)])
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        created, eid = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(created), uuid.UUID(eid)
    except (ValueError, TypeError) as exc:
        raise AppError("invalid_cursor", "Cursor de paginação inválido.", 422) from exc


async def list_essays(
    session: AsyncSession, user: User, limit: int, cursor: str | None
) -> EssayPage:
    stmt = (
        select(Essay, EssayTheme.title, EssayResult.total, EssayResult.annulled)
        .outerjoin(EssayTheme, EssayTheme.id == Essay.theme_id)
        .outerjoin(EssayResult, EssayResult.essay_id == Essay.id)
        .where(Essay.user_id == user.id)
        .order_by(Essay.created_at.desc(), Essay.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        created, eid = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(Essay.created_at < created, and_(Essay.created_at == created, Essay.id < eid))
        )
    rows = (await session.execute(stmt)).all()
    items = [
        EssaySummary(
            id=e.id,
            status=e.status,
            input_type=e.input_type,
            theme_title=title or e.custom_theme or "Tema removido",
            total=total,
            annulled=annulled,
            created_at=e.created_at,
            graded_at=e.graded_at,
        )
        for e, title, total, annulled in rows[:limit]
    ]
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1][0]
        next_cursor = _encode_cursor(last.created_at, last.id)
    return EssayPage(items=items, next_cursor=next_cursor)


async def stats(session: AsyncSession, user: User) -> StatsOut:
    rows = (
        await session.execute(
            select(Essay, EssayResult, EssayTheme.title)
            .join(EssayResult, EssayResult.essay_id == Essay.id)
            .outerjoin(EssayTheme, EssayTheme.id == Essay.theme_id)
            .where(Essay.user_id == user.id, Essay.status == EssayStatus.graded)
            .order_by(Essay.graded_at)
        )
    ).all()
    points = [
        StatsPoint(
            essay_id=e.id,
            date=e.graded_at.date(),
            graded_at=e.graded_at,
            theme_title=title or e.custom_theme or "Tema removido",
            c1=r.c1,
            c2=r.c2,
            c3=r.c3,
            c4=r.c4,
            c5=r.c5,
            total=r.total,
            annulled=r.annulled,
        )
        for e, r, title in rows
        if e.graded_at is not None
    ]
    valid = [p for p in points if not p.annulled]
    averages = None
    if valid:
        averages = {
            k: round(sum(getattr(p, k) for p in valid) / len(valid), 1)
            for k in ("c1", "c2", "c3", "c4", "c5", "total")
        }
    return StatsOut(points=points, averages=averages)


# ---- revisão e confirmação ----------------------------------------------------


def _require_status(essay: Essay, *allowed: EssayStatus) -> None:
    if essay.status not in allowed:
        raise AppError(
            "invalid_status",
            "Esta ação não está disponível no estado atual da redação.",
            409,
            {"status": essay.status},
        )


async def save_transcription(
    session: AsyncSession, user: User, essay_id: uuid.UUID, text: str
) -> Essay:
    essay = await get_owned(session, user, essay_id)
    _require_status(essay, EssayStatus.awaiting_review)
    essay.transcription_text = normalize_text(text)
    await session.commit()
    return essay


async def confirm(
    session: AsyncSession, user: User, essay_id: uuid.UUID, text: str | None
) -> Essay:
    essay = await get_owned(session, user, essay_id)
    _require_status(essay, EssayStatus.awaiting_review)
    if text is not None:
        essay.transcription_text = normalize_text(text)
    markers = find_markers(essay.transcription_text or "")
    if markers:
        raise AppError(
            "unresolved_markers",
            "Ainda há trechos marcados como ilegíveis ou duvidosos. Corrija-os antes de confirmar.",
            422,
            {"markers": [{"line": line, "marker": m} for line, m in markers]},
        )
    if not (essay.transcription_text or "").strip():
        raise AppError("empty_text", "O texto está vazio.", 422)
    essay.confirmed_at = utcnow()
    essay.status = EssayStatus.grading
    await enqueue(
        session, "essay.grade", {"essay_id": str(essay.id)}, max_attempts=AI_JOB_MAX_ATTEMPTS
    )
    await session.commit()
    return essay


async def retry(session: AsyncSession, user: User, essay_id: uuid.UUID) -> Essay:
    essay = await get_owned(session, user, essay_id)
    _require_status(essay, EssayStatus.failed)
    essay.error_message = None
    if essay.confirmed_at is None:
        essay.status = EssayStatus.uploaded
        queue = "essay.transcribe"
    else:
        essay.status = EssayStatus.grading
        queue = "essay.grade"
    await enqueue(session, queue, {"essay_id": str(essay.id)}, max_attempts=AI_JOB_MAX_ATTEMPTS)
    await session.commit()
    return essay


async def delete_essay(
    session: AsyncSession, storage: LocalStorage, user: User, essay_id: uuid.UUID
) -> None:
    essay = await get_owned(session, user, essay_id)
    prefix = essay_prefix(user.id, essay.id)
    await session.execute(delete(Essay).where(Essay.id == essay.id))
    await session.commit()
    try:
        await storage.delete_prefix(prefix)
    except Exception:  # o registro já foi apagado; a limpeza pode ser refeita depois
        logger.exception("essay_storage_cleanup_failed")
