from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.model_version import ModelVersionRead
from app.services import analysis_service

router = APIRouter(prefix="/model-versions", tags=["model-versions"])


@router.get("", response_model=list[ModelVersionRead], summary="Listar versiones de modelo")
def list_model_versions(db: DbSession, active_only: bool = False) -> list[ModelVersionRead]:
    return [
        ModelVersionRead.model_validate(m)
        for m in analysis_service.list_model_versions(db, active_only)
    ]
