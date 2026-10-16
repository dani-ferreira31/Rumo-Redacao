import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user, require_feature, require_verified_user
from app.modules.essays import service
from app.modules.essays.schemas import (
    ConfirmIn,
    EssayOut,
    EssayPage,
    StatsOut,
    ThemeOut,
    TranscriptionIn,
)
from app.modules.users.models import User
from app.storage import LocalStorage, get_storage

router = APIRouter(tags=["essays"], dependencies=[Depends(require_feature("essays"))])


@router.get("/essay-themes", response_model=list[ThemeOut])
async def list_themes(
    year: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_themes(session, year)


@router.post("/essays", response_model=EssayOut, status_code=status.HTTP_202_ACCEPTED)
async def create_essay(
    theme_id: uuid.UUID | None = Form(default=None),
    custom_theme: str | None = Form(default=None),
    text: str | None = Form(default=None),
    images: list[UploadFile] | None = File(default=None),
    user: User = Depends(require_verified_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Envia 1 ou 2 fotos (`images`) **ou** o texto digitado (`text`)."""
    uploads = [
        service.Upload(img.filename or "imagem", img.content_type, await img.read())
        for img in images or []
        if img.filename or img.size
    ]
    essay = await service.create_essay(
        session,
        storage,
        user,
        theme_id=theme_id,
        custom_theme=custom_theme,
        images=uploads,
        text=text,
    )
    return await service.essay_out(session, storage, essay)


@router.get("/essays", response_model=EssayPage)
async def list_essays(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_essays(session, user, limit, cursor)


@router.get("/essays/stats", response_model=StatsOut)
async def essay_stats(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    """Evolução das notas por competência (redações corrigidas)."""
    return await service.stats(session, user)


@router.get("/essays/{essay_id}", response_model=EssayOut)
async def get_essay(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    essay = await service.get_owned(session, user, essay_id)
    return await service.essay_out(session, storage, essay)


@router.put("/essays/{essay_id}/transcription", response_model=EssayOut)
async def save_transcription(
    essay_id: uuid.UUID,
    data: TranscriptionIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    essay = await service.save_transcription(session, user, essay_id, data.text)
    return await service.essay_out(session, storage, essay)


@router.post("/essays/{essay_id}/confirm", response_model=EssayOut)
async def confirm(
    essay_id: uuid.UUID,
    data: ConfirmIn | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Confirma a transcrição revisada e inicia a correção."""
    essay = await service.confirm(session, user, essay_id, data.text if data else None)
    return await service.essay_out(session, storage, essay)


@router.post("/essays/{essay_id}/retry", response_model=EssayOut)
async def retry(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    essay = await service.retry(session, user, essay_id)
    return await service.essay_out(session, storage, essay)


@router.delete("/essays/{essay_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_essay(
    essay_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    await service.delete_essay(session, storage, user, essay_id)
