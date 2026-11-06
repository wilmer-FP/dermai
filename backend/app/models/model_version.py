from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, JSONType, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class ModelVersion(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Versión registrada de un modelo experimental de IA (trazabilidad)."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("name", "version"),)

    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(50))
    architecture: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    weights_path: Mapped[str | None] = mapped_column(String(500))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    analyses: Mapped[list[Analysis]] = relationship(back_populates="model_version")

    def __repr__(self) -> str:
        return f"<ModelVersion {self.name}:{self.version}>"
