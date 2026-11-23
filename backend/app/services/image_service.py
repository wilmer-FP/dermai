"""Carga, validación, consulta y borrado de imágenes."""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from io import BytesIO

from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import (
    InvalidImageError,
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)
from app.models import Image
from app.services.metadata import strip_metadata
from app.services.storage import LocalStorage

logger = logging.getLogger("dermai")

# Formato detectado por Pillow -> (extensión guardada, tipo MIME, extensiones equivalentes)
SUPPORTED_FORMATS: dict[str, tuple[str, str, set[str]]] = {
    "JPEG": ("jpg", "image/jpeg", {"jpg", "jpeg"}),
    "PNG": ("png", "image/png", {"png"}),
}


@dataclass(frozen=True)
class ValidatedImage:
    extension: str
    content_type: str
    width: int
    height: int
    pil_format: str


def sanitize_filename(filename: str) -> str:
    """Conserva solo el nombre base (sin rutas) y lo limita a 255 caracteres."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return (name or "imagen")[:255]


def validate_image(data: bytes, filename: str, settings: Settings) -> ValidatedImage:
    if not data:
        raise InvalidImageError("El archivo está vacío.")
    if len(data) > settings.max_upload_size_bytes:
        raise PayloadTooLargeError(
            f"El archivo supera el tamaño máximo de {settings.max_upload_size_mb} MB."
        )

    allowed = settings.allowed_extensions
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in allowed:
        raise UnsupportedMediaTypeError(
            f"Extensión no permitida. Formatos aceptados: {', '.join(sorted(allowed))}."
        )

    try:
        with PILImage.open(BytesIO(data)) as img:
            detected_format = img.format
            width, height = img.size
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, PILImage.DecompressionBombError) as exc:
        raise InvalidImageError("El archivo no es una imagen válida o está dañado.") from exc

    info = SUPPORTED_FORMATS.get(detected_format or "")
    if info is None or not (info[2] & allowed):
        raise UnsupportedMediaTypeError(
            f"El contenido del archivo ({detected_format}) no es un formato de imagen permitido."
        )

    stored_extension, content_type, _ = info
    return ValidatedImage(stored_extension, content_type, width, height, detected_format or "")


def create_image(
    db: Session,
    storage: LocalStorage,
    settings: Settings,
    filename: str,
    data: bytes,
    session_id: str | None = None,
) -> Image:
    """Valida la imagen, elimina sus metadatos (EXIF, GPS, texto) y la guarda.

    El tamaño, las dimensiones y el SHA-256 corresponden al archivo guardado, ya sin metadatos.
    `session_id` (modo demo) asocia la imagen al navegador que la sube.
    """
    original_filename = sanitize_filename(filename)
    validated = validate_image(data, original_filename, settings)
    try:
        clean = strip_metadata(data, validated.pil_format)
    except (OSError, ValueError, SyntaxError) as exc:
        raise InvalidImageError("El archivo no es una imagen válida o está dañado.") from exc

    image = Image(
        original_filename=original_filename,
        stored_filename=f"{uuid.uuid4().hex}.{validated.extension}",
        content_type=validated.content_type,
        file_size_bytes=len(clean.data),
        width=clean.width,
        height=clean.height,
        checksum_sha256=hashlib.sha256(clean.data).hexdigest(),
        session_id=session_id,
    )

    storage.save(image.stored_filename, clean.data)
    try:
        db.add(image)
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(image.stored_filename)
        raise

    db.refresh(image)
    logger.info("Imagen cargada id=%s (%d bytes)", image.id, image.file_size_bytes)
    return image


def list_images(db: Session, limit: int, offset: int, session_id: str | None = None) -> tuple[list[Image], int]:
    query = select(Image)
    if session_id is not None:
        query = query.where(Image.session_id == session_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Image.created_at.desc(), Image.id).limit(limit).offset(offset)).all()
    return list(items), total


def get_image(db: Session, image_id: uuid.UUID, session_id: str | None = None) -> Image:
    """Devuelve la imagen. En modo demo, una imagen de otra sesión se trata como inexistente."""
    image = db.get(Image, image_id)
    if image is None or (session_id is not None and image.session_id != session_id):
        raise NotFoundError("Imagen no encontrada.")
    return image


def delete_image(db: Session, storage: LocalStorage, image_id: uuid.UUID, session_id: str | None = None) -> None:
    image = get_image(db, image_id, session_id)
    filenames = [image.stored_filename] + [
        a.processed_image_filename for a in image.analyses if a.processed_image_filename
    ]

    db.delete(image)
    db.commit()

    for filename in filenames:
        storage.delete(filename)
    logger.info("Imagen eliminada id=%s", image_id)
