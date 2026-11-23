"""Carga de pares imagen/máscara en formato WoundTissue (carpetas `image/` y `label/`)."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .classes import WOUNDTISSUE_CLASSES, TissueClass, decode_color_mask

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@dataclass(frozen=True)
class Sample:
    name: str
    image_path: Path
    mask_path: Path


def find_samples(root: str | Path) -> list[Sample]:
    """Empareja `root/image/<nombre>` con `root/label/<nombre>` (mismo nombre de archivo)."""
    root = Path(root)
    image_dir, label_dir = root / "image", root / "label"
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise FileNotFoundError(f"No se encuentran las carpetas image/ y label/ en {root}")

    samples = []
    for image_path in sorted(image_dir.iterdir()):
        if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        mask_path = label_dir / image_path.name
        if not mask_path.is_file():
            raise FileNotFoundError(f"Falta la máscara de {image_path.name}")
        samples.append(Sample(image_path.stem, image_path, mask_path))
    if not samples:
        raise FileNotFoundError(f"No hay imágenes en {image_dir}")
    return samples


def read_rgb(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"No se pudo leer {path}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def read_sample(
    sample: Sample, classes: tuple[TissueClass, ...] = WOUNDTISSUE_CLASSES
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve la imagen RGB (uint8) y la máscara de índices (int64) del mismo tamaño."""
    image = read_rgb(sample.image_path)
    mask = decode_color_mask(read_rgb(sample.mask_path), classes)
    if mask.shape != image.shape[:2]:
        raise ValueError(f"La máscara de {sample.name} no tiene el tamaño de la imagen.")
    return image, mask
