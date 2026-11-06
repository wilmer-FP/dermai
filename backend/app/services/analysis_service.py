"""Creación y consulta de análisis y versiones de modelo."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Analysis, AnalysisStatus, Image, ModelVersion
from app.services.image_service import get_image
from app.services.processing_service import run_analysis
from app.services.storage import LocalStorage


def create_analysis(
    db: Session,
    storage: LocalStorage,
    image_id: uuid.UUID,
    model_version_id: uuid.UUID | None = None,
    device: str = "cpu",
    session_id: str | None = None,
) -> Analysis:
    """
    Registra un análisis y lo procesa.

    Sin `model_version_id` se usa la heurística de OpenCV; con él, el modelo de esa versión.
    """
    get_image(db, image_id, session_id)
    if model_version_id is not None and db.get(ModelVersion, model_version_id) is None:
        raise NotFoundError("Versión de modelo no encontrada.")

    analysis = Analysis(
        image_id=image_id,
        model_version_id=model_version_id,
        status=AnalysisStatus.PENDING,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return run_analysis(db, storage, analysis, device)


def list_analyses(
    db: Session,
    limit: int,
    offset: int,
    status: AnalysisStatus | None = None,
    image_id: uuid.UUID | None = None,
    session_id: str | None = None,
) -> tuple[list[Analysis], int]:
    query = select(Analysis)
    if status is not None:
        query = query.where(Analysis.status == status)
    if image_id is not None:
        query = query.where(Analysis.image_id == image_id)
    if session_id is not None:
        query = query.join(Image, Analysis.image_id == Image.id).where(Image.session_id == session_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(Analysis.created_at.desc(), Analysis.id).limit(limit).offset(offset)
    ).all()
    return list(items), total


def get_analysis(db: Session, analysis_id: uuid.UUID, session_id: str | None = None) -> Analysis:
    """Devuelve el análisis. En modo demo, uno de otra sesión se trata como inexistente."""
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or (session_id is not None and analysis.image.session_id != session_id):
        raise NotFoundError("Análisis no encontrado.")
    return analysis


def list_model_versions(db: Session, active_only: bool = False) -> list[ModelVersion]:
    query = select(ModelVersion).order_by(ModelVersion.created_at.desc(), ModelVersion.id)
    if active_only:
        query = query.where(ModelVersion.is_active.is_(True))
    return list(db.scalars(query).all())
