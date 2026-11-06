"""Imágenes sintéticas con resultado conocido para probar el pipeline (no son imágenes clínicas)."""

import cv2
import numpy as np

# Colores BGR
LIGHT_SKIN = (150, 170, 215)
DARK_SKIN = (55, 75, 110)
RED = (70, 70, 190)
YELLOW = (90, 200, 225)
BLACK = (25, 30, 35)

SIZE = (480, 640)  # alto, ancho
CENTER = (320, 240)
OUTER, MIDDLE, INNER = (200, 140), (130, 90), (70, 50)


def add_noise(image: np.ndarray, sigma: float = 6.0, seed: int = 0) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, sigma, image.shape)
    return np.clip(image + noise, 0, 255).astype(np.uint8)


def ellipse_mask(axes: tuple[int, int], shape: tuple[int, int] = SIZE) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    cv2.ellipse(mask, CENTER, axes, 0, 0, 360, 1, -1)
    return mask.astype(bool)


def wound() -> np.ndarray:
    """Herida con tres anillos: rojo (fuera), amarillo y negro (centro), sobre piel clara.

    Proporciones esperadas sobre la elipse exterior: negro ≈ 0.125, amarillo ≈ 0.293, rojo ≈ 0.582.
    """
    image = np.full((*SIZE, 3), LIGHT_SKIN, np.uint8)
    cv2.ellipse(image, CENTER, OUTER, 0, 0, 360, RED, -1)
    cv2.ellipse(image, CENTER, MIDDLE, 0, 0, 360, YELLOW, -1)
    cv2.ellipse(image, CENTER, INNER, 0, 0, 360, BLACK, -1)
    return add_noise(image)


def expected_ratios() -> dict[str, float]:
    outer = np.pi * OUTER[0] * OUTER[1]
    middle = np.pi * MIDDLE[0] * MIDDLE[1]
    inner = np.pi * INNER[0] * INNER[1]
    return {"necrotic": inner / outer, "slough": (middle - inner) / outer, "granulation": (outer - middle) / outer}


def single_lesion(skin: tuple[int, int, int], lesion: tuple[int, int, int], axes=OUTER) -> np.ndarray:
    image = np.full((*SIZE, 3), skin, np.uint8)
    cv2.ellipse(image, CENTER, axes, 0, 0, 360, lesion, -1)
    return add_noise(image)


def write_segmentation_dataset(root, count: int = 6, size: int = 64) -> None:
    """Dataset sintético en formato WoundTissue: image/*.png y label/*.png con la paleta de clases."""
    from pathlib import Path

    from ai.models.classes import WOUNDTISSUE_CLASSES

    root = Path(root)
    (root / "image").mkdir(parents=True)
    (root / "label").mkdir(parents=True)
    palette = {c.key: c.mask_color for c in WOUNDTISSUE_CLASSES}
    rng = np.random.default_rng(0)
    for index in range(count):
        image = np.full((size, size, 3), (150, 170, 215), np.uint8)  # BGR piel
        label = np.zeros((size, size, 3), np.uint8)
        label[:] = palette["background"][::-1]  # RGB -> BGR para cv2.imwrite
        center = (int(rng.integers(20, size - 20)), int(rng.integers(20, size - 20)))
        cv2.circle(image, center, 16, RED, -1)
        cv2.circle(label, center, 16, palette["granulation"][::-1], -1)
        cv2.circle(image, center, 7, BLACK, -1)
        cv2.circle(label, center, 7, palette["necrosis"][::-1], -1)
        cv2.imwrite(str(root / "image" / f"img{index}.png"), add_noise(image, seed=index))
        cv2.imwrite(str(root / "label" / f"img{index}.png"), label)


def uniform(color: tuple[int, int, int] = LIGHT_SKIN, shape: tuple[int, int] = SIZE) -> np.ndarray:
    return add_noise(np.full((*shape, 3), color, np.uint8), sigma=2.0)
