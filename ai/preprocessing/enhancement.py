"""Normalización de tamaño y color, reducción de ruido y conversión de espacios de color."""

import cv2
import numpy as np


def resize_longest_side(image: np.ndarray, target: int) -> np.ndarray:
    """Escala la imagen para que su lado mayor mida `target` píxeles, conservando la proporción."""
    height, width = image.shape[:2]
    scale = target / max(height, width)
    if scale == 1:
        return image.copy()
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(image, size, interpolation=interpolation)


def shades_of_gray(
    image: np.ndarray, power: float = 6.0, mask: np.ndarray | None = None, strength: float = 1.0
) -> np.ndarray:
    """Constancia de color "Shades of Gray" (Finlayson y Trezzi, 2004).

    Estima el color de la iluminación con la norma de Minkowski de orden `power` y lo
    corrige para que sea neutro. Con p = 6 es un método habitual en imagen dermatológica
    (Barata et al., 2015). `mask` limita la estimación a ciertos píxeles (p. ej. sin reflejos).
    `strength` entre 0 y 1 aplica la corrección de forma parcial (ganancias elevadas a `strength`).
    """
    pixels = image.reshape(-1, 3) if mask is None or not mask.any() else image[mask]
    pixels = pixels.astype(np.float64)
    norm = np.power(np.mean(np.power(pixels, power), axis=0), 1.0 / power)
    if not np.all(np.isfinite(norm)) or np.any(norm <= 0):
        return image.copy()
    illuminant = norm / np.linalg.norm(norm)
    gains = np.power(1.0 / (illuminant * np.sqrt(3.0)), float(np.clip(strength, 0.0, 1.0)))
    return np.clip(image.astype(np.float64) * gains, 0, 255).astype(np.uint8)


def denoise(image: np.ndarray, diameter: int, sigma_color: float, sigma_space: float) -> np.ndarray:
    """Filtro bilateral: suaviza el ruido sin borrar los bordes de la lesión."""
    return cv2.bilateralFilter(image, diameter, sigma_color, sigma_space)


def to_lab(image: np.ndarray) -> np.ndarray:
    """BGR (uint8) a CIELAB en coma flotante: L* en 0–100, a* y b* aprox. en −128–127."""
    return cv2.cvtColor(image.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)


def to_gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
