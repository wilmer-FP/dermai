import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import DbSession, Limit, Offset, SessionId, StorageDep
from app.core.exceptions import NotFoundError
from app.models import AnalysisStatus
from app.schemas.analysis import AnalysisRead
from app.schemas.common import ErrorResponse, Page
from app.services import analysis_service

router = APIRouter(prefix="/analyses", tags=["analyses"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Análisis no encontrado"}}


@router.get("", response_model=Page[AnalysisRead], summary="Historial de análisis")
def list_analyses(
    db: DbSession,
    session_id: SessionId,
    status: AnalysisStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> Page[AnalysisRead]:
    """Lista los análisis, del más reciente al más antiguo. Se puede filtrar por estado.

    En modo demo solo se listan los de la sesión del visitante.
    """
    items, total = analysis_service.list_analyses(db, limit, offset, status=status, session_id=session_id)
    return Page[AnalysisRead](
        items=[AnalysisRead.model_validate(a) for a in items], total=total, limit=limit, offset=offset
    )


@router.get(
    "/{analysis_id}",
    response_model=AnalysisRead,
    summary="Obtener un análisis",
    responses=NOT_FOUND,
)
def get_analysis(analysis_id: uuid.UUID, db: DbSession, session_id: SessionId) -> AnalysisRead:
    return AnalysisRead.model_validate(analysis_service.get_analysis(db, analysis_id, session_id))


@router.get(
    "/{analysis_id}/processed-image",
    response_class=FileResponse,
    summary="Descargar la imagen procesada",
    responses={404: {"model": ErrorResponse, "description": "Análisis o imagen procesada no encontrados"}},
)
def get_processed_image(
    analysis_id: uuid.UUID, db: DbSession, storage: StorageDep, session_id: SessionId
) -> FileResponse:
    """PNG con la región analizada (contorno verde), los tejidos marcados y el aviso de uso no diagnóstico."""
    analysis = analysis_service.get_analysis(db, analysis_id, session_id)
    filename = analysis.processed_image_filename
    if not filename or not storage.exists(filename):
        raise NotFoundError("El análisis no tiene imagen procesada.")
    return FileResponse(storage.path_for(filename), media_type="image/png")
