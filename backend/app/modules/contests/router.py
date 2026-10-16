"""Rotas de concursos: importação e revisão (admin) e filtros (aluno)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import require_admin, require_feature
from app.modules.contests import service
from app.modules.contests.schemas import (
    ContestExamDetail,
    ContestExamOut,
    ContestFiltersOut,
    ContestMetaIn,
    EstimateOut,
    FigureIn,
    SubjectIn,
)
from app.modules.users.models import User
from app.storage import LocalStorage, get_storage

router = APIRouter(tags=["contests"])
admin = APIRouter(prefix="/admin/contests", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get(
    "/contests/filters",
    response_model=ContestFiltersOut,
    dependencies=[Depends(require_feature("questions_concursos"))],
)
async def contest_filters(session: AsyncSession = Depends(get_session)):
    """Bancas, órgãos, cargos e anos das provas publicadas."""
    return await service.public_filters(session)


@admin.post("/estimate", response_model=EstimateOut)
async def estimate(exam_pdf: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """Páginas e custo estimado da importação, antes de confirmar."""
    return await service.estimate(session, await exam_pdf.read())


@admin.post("", response_model=ContestExamOut, status_code=status.HTTP_202_ACCEPTED)
async def create(
    board: str = Form(...),
    organization: str = Form(...),
    position: str = Form(...),
    year: int = Form(...),
    level: str | None = Form(default=None),
    booklet: str | None = Form(default=None),
    exam_pdf: UploadFile = File(...),
    answer_key_pdf: UploadFile | None = File(default=None),
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Envia o PDF da prova (e, se tiver, o do gabarito). A leitura roda na fila."""
    meta = ContestMetaIn(
        board=board,
        organization=organization,
        position=position,
        year=year,
        level=level or None,
        booklet=booklet or None,
    )
    key_bytes = await answer_key_pdf.read() if answer_key_pdf and answer_key_pdf.filename else None
    exam = await service.create(session, storage, user, meta, await exam_pdf.read(), key_bytes)
    return ContestExamOut(**service.exam_out(exam))


@admin.get("", response_model=list[ContestExamOut])
async def list_exams(session: AsyncSession = Depends(get_session)):
    return await service.list_exams(session)


@admin.get("/{exam_id}", response_model=ContestExamDetail)
async def detail(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    return await service.detail(session, storage, exam_id)


@admin.put("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_meta(
    exam_id: int, data: ContestMetaIn, session: AsyncSession = Depends(get_session)
):
    await service.update_meta(session, exam_id, data)


@admin.post("/{exam_id}/publish", status_code=status.HTTP_204_NO_CONTENT)
async def publish(exam_id: int, session: AsyncSession = Depends(get_session)):
    await service.publish(session, exam_id)


@admin.post("/{exam_id}/unpublish", status_code=status.HTTP_204_NO_CONTENT)
async def unpublish(exam_id: int, session: AsyncSession = Depends(get_session)):
    await service.unpublish(session, exam_id)


@admin.post("/{exam_id}/retry", status_code=status.HTTP_204_NO_CONTENT)
async def retry(exam_id: int, session: AsyncSession = Depends(get_session)):
    await service.retry(session, exam_id)


@admin.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(
    exam_id: int,
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    await service.remove(session, storage, exam_id)


@admin.post("/{exam_id}/questions/{question_id}/figure", status_code=status.HTTP_204_NO_CONTENT)
async def add_figure(
    exam_id: int,
    question_id: int,
    data: FigureIn,
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Recorta uma área da página e coloca como imagem no enunciado."""
    await service.add_figure(session, storage, exam_id, question_id, data)


@admin.post("/subjects", status_code=status.HTTP_201_CREATED)
async def create_subject(data: SubjectIn, session: AsyncSession = Depends(get_session)) -> dict:
    return {"id": await service.create_subject(session, data.name)}


router.include_router(admin)
