"""Clases de tejido del dataset WoundTissue y conversión entre máscaras de color e índices."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TissueClass:
    index: int
    key: str
    label: str
    mask_color: tuple[int, int, int]  # RGB en las máscaras del dataset
    display_color: tuple[int, int, int]  # RGB en la imagen procesada (visible sobre la piel)
    group: str  # grupo común con la heurística: background, necrotic, slough, granulation, other


WOUNDTISSUE_CLASSES: tuple[TissueClass, ...] = (
    TissueClass(0, "background", "Fondo", (0, 0, 255), (0, 0, 0), "background"),
    TissueClass(1, "granulation", "Granulación", (255, 0, 0), (230, 40, 40), "granulation"),
    TissueClass(2, "slough", "Esfacelo", (255, 255, 0), (255, 215, 0), "slough"),
    TissueClass(3, "necrosis", "Necrosis", (0, 0, 0), (255, 0, 255), "necrotic"),
    TissueClass(4, "maceration", "Maceración", (255, 255, 255), (235, 235, 235), "other"),
    # El color del tendón no aparece en la muestra pública; se supone azul cielo.
    TissueClass(5, "tendon", "Tendón", (135, 206, 235), (135, 206, 235), "other"),
    TissueClass(6, "bone", "Hueso", (255, 200, 124), (255, 200, 124), "other"),
)

# Grupos comunes para comparar el modelo con la heurística de ai/preprocessing.
GROUPS: tuple[str, ...] = ("background", "granulation", "slough", "necrotic", "other")


def decode_color_mask(
    rgb: np.ndarray, classes: tuple[TissueClass, ...] = WOUNDTISSUE_CLASSES, max_distance: float = 60.0
) -> np.ndarray:
    """Convierte una máscara RGB en índices de clase asignando cada píxel al color más cercano.

    Lanza ValueError si algún píxel está a más de `max_distance` de todos los colores conocidos
    (máscara con un color inesperado).
    """
    palette = np.array([c.mask_color for c in classes], dtype=np.float32)
    pixels = rgb[..., :3].reshape(-1, 3).astype(np.float32)
    distances = np.linalg.norm(pixels[:, None, :] - palette[None, :, :], axis=2)
    nearest = distances.argmin(axis=1)
    if distances[np.arange(len(pixels)), nearest].max(initial=0.0) > max_distance:
        raise ValueError("La máscara contiene colores que no corresponden a ninguna clase.")
    return nearest.reshape(rgb.shape[:2]).astype(np.int64)


def group_indices(labels: np.ndarray, classes: tuple[TissueClass, ...] = WOUNDTISSUE_CLASSES) -> np.ndarray:
    """Convierte índices de clase en índices de `GROUPS`."""
    lookup = np.array([GROUPS.index(c.group) for c in classes], dtype=np.int64)
    return lookup[labels]
