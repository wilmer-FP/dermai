from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class Image(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """
    Fotografía cargada en el sistema.

    Solo se guardan metadatos técnicos del archivo. El archivo en sí reside en
    STORAGE_PATH bajo `stored_filename`. No se almacenan datos personales.
    """

    __tablename__ = "images"
    __table_args__ = (
        CheckConstraint("file_size_bytes > 0", name="file_size_positive"),
        CheckConstraint("width IS NULL OR width > 0", name="width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="height_positive"),
    )

    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    # Solo en modo demo: identificador anónimo del navegador que subió la imagen.
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)

    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="image",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Image id={self.id} file={self.stored_filename!r}>"
