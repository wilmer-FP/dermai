"""Aumento de datos y normalización (NumPy/OpenCV) para entrenamiento e inferencia."""

import cv2
import numpy as np

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def normalize(image_rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 (H, W, 3) a float32 (3, H, W) normalizado con la media y desviación de ImageNet."""
    scaled = image_rgb.astype(np.float32) / 255.0
    return ((scaled - IMAGENET_MEAN) / IMAGENET_STD).transpose(2, 0, 1).copy()


def resize_longest(image: np.ndarray, size: int, interpolation: int = cv2.INTER_LINEAR) -> np.ndarray:
    height, width = image.shape[:2]
    scale = size / max(height, width)
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(image, target, interpolation=interpolation)


def random_resized_crop(
    image: np.ndarray,
    mask: np.ndarray,
    size: int,
    rng: np.random.Generator,
    scale: tuple[float, float] = (0.5, 1.0),
    ratio: tuple[float, float] = (3 / 4, 4 / 3),
) -> tuple[np.ndarray, np.ndarray]:
    height, width = mask.shape
    area = height * width
    for _ in range(10):
        target_area = area * rng.uniform(*scale)
        aspect = np.exp(rng.uniform(np.log(ratio[0]), np.log(ratio[1])))
        crop_w = int(round(np.sqrt(target_area * aspect)))
        crop_h = int(round(np.sqrt(target_area / aspect)))
        if 0 < crop_w <= width and 0 < crop_h <= height:
            top = int(rng.integers(0, height - crop_h + 1))
            left = int(rng.integers(0, width - crop_w + 1))
            break
    else:
        crop_h, crop_w, top, left = height, width, 0, 0
    image = image[top : top + crop_h, left : left + crop_w]
    mask = mask[top : top + crop_h, left : left + crop_w]
    return (
        cv2.resize(image, (size, size), interpolation=cv2.INTER_LINEAR),
        cv2.resize(mask.astype(np.uint8), (size, size), interpolation=cv2.INTER_NEAREST).astype(np.int64),
    )


def color_jitter(
    image: np.ndarray, rng: np.random.Generator, strength: float = 0.15, hue_degrees: float = 4.0
) -> np.ndarray:
    """Variaciones leves de brillo, contraste, saturación y tono (el color es informativo: se cambia poco)."""
    result = image.astype(np.float32)
    result *= rng.uniform(1 - strength, 1 + strength)  # brillo
    mean = result.mean()
    result = (result - mean) * rng.uniform(1 - strength, 1 + strength) + mean  # contraste
    hsv = cv2.cvtColor(np.clip(result, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 0] = (hsv[..., 0] + rng.uniform(-hue_degrees, hue_degrees) / 2) % 180  # OpenCV: tono 0–179
    hsv[..., 1] *= rng.uniform(1 - strength, 1 + strength)
    hsv = np.clip(hsv, 0, [179, 255, 255]).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def augment(image: np.ndarray, mask: np.ndarray, size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Recorte aleatorio, volteos, rotaciones de 90° y variación de color."""
    image, mask = random_resized_crop(image, mask, size, rng)
    if rng.random() < 0.5:
        image, mask = image[:, ::-1], mask[:, ::-1]
    if rng.random() < 0.5:
        image, mask = image[::-1], mask[::-1]
    turns = int(rng.integers(0, 4))
    image, mask = np.rot90(image, turns), np.rot90(mask, turns)
    image = color_jitter(np.ascontiguousarray(image), rng)
    return np.ascontiguousarray(image), np.ascontiguousarray(mask)
