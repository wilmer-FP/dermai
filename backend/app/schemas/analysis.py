import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.constants import DISCLAIMER
from app.models import AnalysisStatus


class AnalysisCreate(BaseModel):
    model_version_id: uuid.UUID | None = None


class AnalysisRead(BaseModel):
    """Resultado experimental de un análisis. No constituye un diagnóstico médico."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_id: uuid.UUID
    model_version_id: uuid.UUID | None
    status: AnalysisStatus
    necrotic_area_ratio: float | None
    confidence: float | None
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    # Nombre interno del archivo: no se expone, solo se usa para `has_processed_image`.
    processed_image_filename: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_processed_image(self) -> bool:
        """Si hay imagen procesada disponible en GET /analyses/{id}/processed-image."""
        return self.processed_image_filename is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def disclaimer(self) -> str:
        return DISCLAIMER
