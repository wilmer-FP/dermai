from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, JSONType, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.image import Image
    from app.models.model_version import ModelVersion


class AnalysisStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Analysis(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """
    Ejecución del pipeline de análisis sobre una imagen.

    Los valores numéricos son salidas experimentales, nunca un diagnóstico.
    """

    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(
            "necrotic_area_ratio IS NULL OR (necrotic_area_ratio >= 0 AND necrotic_area_ratio <= 1)",
            name="necrotic_area_ratio_range",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
    )

    image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("images.id", ondelete="CASCADE"), index=True
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(
            AnalysisStatus,
            name="analysis_status",
            values_callable=lambda e: [member.value for member in e],
        ),
        default=AnalysisStatus.PENDING,
        server_default=AnalysisStatus.PENDING.value,
        index=True,
    )
    necrotic_area_ratio: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    processed_image_filename: Mapped[str | None] = mapped_column(String(255))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    image: Mapped[Image] = relationship(back_populates="analyses")
    model_version: Mapped[ModelVersion | None] = relationship(back_populates="analyses")

    def __repr__(self) -> str:
        return f"<Analysis id={self.id} status={self.status.value}>"
