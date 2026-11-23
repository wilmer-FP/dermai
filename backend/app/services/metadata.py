"""Eliminación de metadatos de las imágenes subidas (privacidad por diseño).

Las fotos de móvil suelen incluir EXIF con ubicación GPS, fecha y modelo de cámara, y los PNG
pueden llevar texto incrustado. Ninguno de esos datos hace falta para el análisis, así que se
eliminan antes de guardar el archivo:

- JPEG: se quitan los segmentos APP1 (EXIF/XMP), APP13 (IPTC) y COM **sin recomprimir**. Se
  conservan JFIF, el perfil de color ICC (APP2) y Adobe (APP14). Si la foto tiene una orientación
  EXIF distinta de la normal, se gira físicamente (recompresión a calidad 95), porque al quitar el
  EXIF se perdería la orientación.
- PNG: se quitan los bloques eXIf, tEXt, zTXt, iTXt y tIME; los píxeles no cambian.
"""

import struct
from dataclasses import dataclass
from io import BytesIO

from PIL import Image as PILImage
from PIL import ImageOps

JPEG_DROPPED_MARKERS = {0xE1, 0xED, 0xFE}  # APP1 (EXIF/XMP), APP13 (IPTC), COM
PNG_DROPPED_CHUNKS = {b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXIF_ORIENTATION = 0x0112


@dataclass(frozen=True)
class CleanImage:
    data: bytes
    width: int
    height: int


class MetadataError(ValueError):
    """La estructura del archivo no permite quitar los metadatos de forma segura."""


def _strip_jpeg_segments(data: bytes) -> bytes:
    if data[:2] != b"\xff\xd8":
        raise MetadataError("No es un JPEG.")
    output = bytearray(data[:2])
    index = 2
    while index < len(data):
        if data[index] != 0xFF:
            raise MetadataError("Marcador JPEG inesperado.")
        while index < len(data) and data[index] == 0xFF:  # bytes de relleno
            index += 1
        if index >= len(data):
            raise MetadataError("JPEG truncado.")
        marker = data[index]
        index += 1
        if marker == 0xDA:  # inicio de los datos de imagen: se copia el resto tal cual
            output += b"\xff\xda" + data[index:]
            return bytes(output)
        if marker in (0x01, *range(0xD0, 0xD8)):  # marcadores sin longitud
            output += bytes((0xFF, marker))
            continue
        if index + 2 > len(data):
            raise MetadataError("JPEG truncado.")
        (length,) = struct.unpack(">H", data[index : index + 2])
        segment_end = index + length
        if length < 2 or segment_end > len(data):
            raise MetadataError("Segmento JPEG con longitud no válida.")
        if marker not in JPEG_DROPPED_MARKERS:
            output += bytes((0xFF, marker)) + data[index:segment_end]
        index = segment_end
    raise MetadataError("JPEG sin datos de imagen.")


def _strip_png_chunks(data: bytes) -> bytes:
    if not data.startswith(PNG_SIGNATURE):
        raise MetadataError("No es un PNG.")
    output = bytearray(PNG_SIGNATURE)
    index = len(PNG_SIGNATURE)
    while index < len(data):
        if index + 8 > len(data):
            raise MetadataError("PNG truncado.")
        (length,) = struct.unpack(">I", data[index : index + 4])
        chunk_type = data[index + 4 : index + 8]
        chunk_end = index + 12 + length
        if chunk_end > len(data):
            raise MetadataError("Bloque PNG con longitud no válida.")
        if chunk_type not in PNG_DROPPED_CHUNKS:
            output += data[index:chunk_end]
        index = chunk_end
        if chunk_type == b"IEND":
            return bytes(output)
    raise MetadataError("PNG sin bloque IEND.")


def _reencode_upright(image: PILImage.Image, fmt: str) -> bytes:
    upright = ImageOps.exif_transpose(image)
    buffer = BytesIO()
    if fmt == "JPEG":
        upright.convert("RGB").save(buffer, format="JPEG", quality=95)
    else:
        upright.save(buffer, format="PNG")
    return buffer.getvalue()


def strip_metadata(data: bytes, fmt: str) -> CleanImage:
    """Devuelve la imagen sin metadatos y sus dimensiones finales. `fmt` es el formato de Pillow."""
    with PILImage.open(BytesIO(data)) as image:
        orientation = image.getexif().get(EXIF_ORIENTATION, 1)
        if orientation not in (1, None):
            cleaned = _reencode_upright(image, fmt)
        else:
            try:
                cleaned = _strip_jpeg_segments(data) if fmt == "JPEG" else _strip_png_chunks(data)
            except MetadataError:
                # Estructura inusual: se recodifica con Pillow, que no copia metadatos.
                cleaned = _reencode_upright(image, fmt)

    with PILImage.open(BytesIO(cleaned)) as result:
        result.load()  # comprueba que el archivo resultante es válido
        return CleanImage(cleaned, result.width, result.height)
