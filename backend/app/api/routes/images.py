import uuid

from fastapi import APIRouter, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import DbSession, Limit, Offset, RateLimited, SessionId, SettingsDep, StorageDep
from app.core.exceptions import NotFoundError
from app.schemas.analysis import AnalysisCreate, AnalysisRead
from app.schemas.common import ErrorResponse, Page
from app.schemas.image import ImageRead
from app.services import analysis_service, image_service

router = APIRouter(prefix="/images", tags=["images"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Imagen no encontrada"}}
DEMO_ERRORS = {
    400: {"model": ErrorResponse, "description": "Modo demo: falta el identificador de sesión"},
    429: {"model": ErrorResponse, "description": "Modo demo: límite de peticiones alcanzado"},
}


@router.post(
    "",
    response_model=ImageRead,
    status_code=status.HTTP_201_CREATED,
    summary="Subir una imagen",
    dependencies=[RateLimited],
    responses={
        413: {"model": ErrorResponse, "description": "Archivo demasiado grande"},
        415: {"model": ErrorResponse, "description": "Formato no permitido"},
        422: {"model": ErrorResponse, "description": "Archivo vacío o imagen no válida"},
        **DEMO_ERRORS,
    },
)
def upload_image(
    file: UploadFile, db: DbSession, storage: StorageDep, settings: SettingsDep, session_id: SessionId
) -> ImageRead:
    """Sube una fotografía JPG o PNG. Se valida el contenido real del archivo, no solo la extensión."""
    # Se lee un byte más del límite para detectar archivos demasiado grandes sin cargarlos enteros.
    data = file.file.read(settings.max_upload_size_bytes + 1)
    image = image_service.create_image(db, storage, settings, file.filename or "", data, session_id)
    return ImageRead.model_validate(image)


@router.get("", response_model=Page[ImageRead], summary="Listar imágenes")
def list_images(db: DbSession, session_id: SessionId, limit: Limit = 20, offset: Offset = 0) -> Page[ImageRead]:
    items, total = image_service.list_images(db, limit, offset, session_id)
    return Page[ImageRead](
        items=[ImageRead.model_validate(i) for i in items], total=total, limit=limit, offset=offset
    )


@router.get("/{image_id}", response_model=ImageRead, summary="Obtener una imagen", responses=NOT_FOUND)
def get_image(image_id: uuid.UUID, db: DbSession, session_id: SessionId) -> ImageRead:
    return ImageRead.model_validate(image_service.get_image(db, image_id, session_id))


@router.get(
    "/{image_id}/file",
    response_class=FileResponse,
    summary="Descargar el archivo de la imagen",
    responses=NOT_FOUND,
)
def get_image_file(image_id: uuid.UUID, db: DbSession, storage: StorageDep, session_id: SessionId) -> FileResponse:
    image = image_service.get_image(db, image_id, session_id)
    if not storage.exists(image.stored_filename):
        raise NotFoundError("El archivo de la imagen no está en el almacenamiento.")
    return FileResponse(storage.path_for(image.stored_filename), media_type=image.content_type)


@router.delete(
    "/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una imagen y sus análisis",
    responses=NOT_FOUND,
)
def delete_image(image_id: uuid.UUID, db: DbSession, storage: StorageDep, session_id: SessionId) -> Response:
    image_service.delete_image(db, storage, image_id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{image_id}/analyses",
    response_model=AnalysisRead,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar un análisis de la imagen",
    dependencies=[RateLimited],
    responses={404: {"model": ErrorResponse, "description": "Imagen o modelo no encontrado"}, **DEMO_ERRORS},
)
def create_analysis(
    image_id: uuid.UUID,
    db: DbSession,
    storage: StorageDep,
    settings: SettingsDep,
    session_id: SessionId,
    payload: AnalysisCreate | None = None,
) -> AnalysisRead:
    """Registra un análisis y lo procesa en la misma petición.

    Sin `model_version_id` se usa la heurística de OpenCV; con él, el modelo de esa versión
    (ver GET /model-versions). Devuelve el análisis en `completed`, o en `failed` con el motivo.
    """
    model_version_id = payload.model_version_id if payload else None
    analysis = analysis_service.create_analysis(
        db, storage, image_id, model_version_id, device=settings.ai_device, session_id=session_id
    )
    return AnalysisRead.model_validate(analysis)


@router.get(
    "/{image_id}/analyses",
    response_model=Page[AnalysisRead],
    summary="Listar los análisis de una imagen",
    responses=NOT_FOUND,
)
def list_image_analyses(
    image_id: uuid.UUID, db: DbSession, session_id: SessionId, limit: Limit = 20, offset: Offset = 0
) -> Page[AnalysisRead]:
    image_service.get_image(db, image_id, session_id)
    items, total = analysis_service.list_analyses(db, limit, offset, image_id=image_id)
    return Page[AnalysisRead](
        items=[AnalysisRead.model_validate(a) for a in items], total=total, limit=limit, offset=offset
    )
