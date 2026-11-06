import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImageRead(BaseModel):
    """Metadatos de una imagen. El archivo se obtiene en GET /images/{id}/file."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    file_size_bytes: int
    width: int | None
    height: int | None
    checksum_sha256: str
    created_at: datetime
