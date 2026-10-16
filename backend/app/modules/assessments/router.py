import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user, require_teacher
from app.modules.assessments import service
from app.modules.assessments.schemas import (
    AssessmentDetail,
    AssessmentIn,
    AssessmentPublic,
    AssessmentResults,
    AssessmentSummary,
    AssessmentUpdate,
    AttemptAnswerIn,
    AttemptOut,
)
from app.modules.users.models import User
from app.storage import LocalStorage, get_storage

router = APIRouter(tags=["assessments"])

# ---- professor ----------------------------------------------------------------------

teacher = APIRouter(prefix="/teacher/assessments")


@teacher.get("", response_model=list[AssessmentSummary])
async def list_assessments(
    user: User = Depends(require_teacher), session: AsyncSession = Depends(get_session)
):
    return await service.list_for_teacher(session, user)


@teacher.post("", response_model=AssessmentDetail, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    data: AssessmentIn,
    user: User = Depends(require_teacher),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Cria a prova fechada; o professor abre quando for aplicar."""
    return await service.create(session, storage, user, data)


@teacher.get("/{assessment_id}", response_model=AssessmentDetail)
async def get_assessment(
    assessment_id: uuid.UUID,
    user: User = Depends(require_teacher),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Prova com gabarito (para conferir e imprimir)."""
    return await service.detail(session, storage, user, assessment_id)


@teacher.patch("/{assessment_id}", response_model=AssessmentDetail)
async def update_assessment(
    assessment_id: uuid.UUID,
    data: AssessmentUpdate,
    user: User = Depends(require_teacher),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    return await service.update(session, storage, user, assessment_id, data)


@teacher.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: uuid.UUID,
    user: User = Depends(require_teacher),
    session: AsyncSession = Depends(get_session),
):
    await service.remove(session, user, assessment_id)


@teacher.get("/{assessment_id}/results", response_model=AssessmentResults)
async def assessment_results(
    assessment_id: uuid.UUID,
    user: User = Depends(require_teacher),
    session: AsyncSession = Depends(get_session),
):
    return await service.results(session, user, assessment_id)


# ---- aluno (qualquer conta logada com o link) ---------------------------------------

student = APIRouter(prefix="/assessments")


@student.get("/by-code/{code}", response_model=AssessmentPublic)
async def assessment_by_code(
    code: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    return await service.public_info(session, user, code)


@student.post("/by-code/{code}/start", response_model=AttemptOut)
async def start_assessment(
    code: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Começa ou retoma a prova (uma tentativa por aluno). Questões sem gabarito."""
    return await service.start(session, storage, user, code)


@student.get("/attempts/{attempt_id}", response_model=AttemptOut)
async def get_attempt(
    attempt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    return await service.get_attempt(session, storage, user, attempt_id)


@student.put("/attempts/{attempt_id}/answers/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def save_answer(
    attempt_id: uuid.UUID,
    question_id: int,
    data: AttemptAnswerIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Grava (ou troca) a resposta. Não devolve se acertou."""
    await service.save_answer(session, user, attempt_id, question_id, data.selected_option)


@student.post("/attempts/{attempt_id}/finish", response_model=AttemptOut)
async def finish_attempt(
    attempt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    storage: LocalStorage = Depends(get_storage),
):
    """Entrega a prova: devolve a nota e o gabarito."""
    return await service.finish(session, storage, user, attempt_id)


router.include_router(teacher)
router.include_router(student)
