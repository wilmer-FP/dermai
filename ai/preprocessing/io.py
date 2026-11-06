"""Lectura y escritura de imágenes en memoria (formato BGR de OpenCV)."""

from pathlib import Path

import cv2
import numpy as np


class ImageDecodeError(ValueError):
    """El contenido no se pudo interpretar como imagen."""


def decode_image(data: bytes) -> np.ndarray:
    """Decodifica JPG/PNG a una matriz BGR de 8 bits y 3 canales.

    Aplica la orientación EXIF, descarta el canal alfa y convierte escala de grises a color.
    """
    if not data:
        raise ImageDecodeError("El archivo de imagen está vacío.")
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ImageDecodeError("No se pudo decodificar la imagen.")
    return image


def load_image(path: str | Path) -> np.ndarray:
    return decode_image(Path(path).read_bytes())


def encode_png(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("No se pudo codificar la imagen como PNG.")
    return buffer.tobytes()
