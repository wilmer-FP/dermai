"""Extracción de características visuales: color, textura, bordes, forma y calidad."""

from typing import Any

import cv2
import numpy as np

GLCM_OFFSETS: tuple[tuple[int, int], ...] = ((0, 1), (1, 1), (1, 0), (1, -1))  # 0°, 45°, 90°, 135°


def _stats(values: np.ndarray) -> tuple[float, float]:
    if values.size == 0:
        return 0.0, 0.0
    return float(values.mean()), float(values.std())


# ---------- Color ----------


def color_features(
    lab: np.ndarray, region: np.ndarray, skin_lab: tuple[float, float, float]
) -> dict[str, Any]:
    """Estadísticos CIELAB de la lesión y su diferencia de color con la piel de referencia."""
    pixels = lab[region]
    l_mean, l_std = _stats(pixels[:, 0])
    a_mean, a_std = _stats(pixels[:, 1])
    b_mean, b_std = _stats(pixels[:, 2])
    chroma_mean, _ = _stats(np.hypot(pixels[:, 1], pixels[:, 2]))
    delta_e = np.linalg.norm(pixels - np.asarray(skin_lab), axis=1) if pixels.size else np.zeros(0)
    return {
        "lesion_lab_mean": [l_mean, a_mean, b_mean],
        "lesion_lab_std": [l_std, a_std, b_std],
        "lesion_chroma_mean": chroma_mean,
        "skin_reference_lab": list(skin_lab),
        "delta_e_to_skin_mean": float(delta_e.mean()) if delta_e.size else 0.0,
    }


# ---------- Textura ----------


def glcm_features(gray: np.ndarray, region: np.ndarray, levels: int = 32) -> dict[str, float]:
    """Descriptores de Haralick de la matriz de co-ocurrencia de grises, solo dentro de `region`.

    Distancia 1, cuatro orientaciones promediadas (invariancia aproximada a la rotación).
    Los grises se cuantizan entre los percentiles 1 y 99 de la región.
    """
    names = ("contrast", "homogeneity", "energy", "correlation", "entropy")
    values = gray[region]
    if values.size < 16:
        return dict.fromkeys(names, 0.0)

    low, high = np.percentile(values, [1, 99])
    if high <= low:
        high = low + 1.0
    quantized = np.clip(((gray.astype(np.float32) - low) / (high - low) * levels).astype(np.int64), 0, levels - 1)
    height, width = gray.shape
    i_idx, j_idx = np.indices((levels, levels))
    accumulated = dict.fromkeys(names, 0.0)
    used = 0

    for dy, dx in GLCM_OFFSETS:
        src_x = slice(0, width - dx) if dx >= 0 else slice(-dx, width)
        dst_x = slice(dx, width) if dx >= 0 else slice(0, width + dx)
        src_y, dst_y = slice(0, height - dy), slice(dy, height)
        pair_mask = region[src_y, src_x] & region[dst_y, dst_x]
        first = quantized[src_y, src_x][pair_mask]
        second = quantized[dst_y, dst_x][pair_mask]
        if first.size == 0:
            continue
        counts = np.bincount(first * levels + second, minlength=levels * levels).reshape(levels, levels)
        matrix = (counts + counts.T).astype(np.float64)
        matrix /= matrix.sum()

        mean = float((i_idx * matrix).sum())
        variance = float((matrix * (i_idx - mean) ** 2).sum())
        nonzero = matrix[matrix > 0]
        accumulated["contrast"] += float((matrix * (i_idx - j_idx) ** 2).sum())
        accumulated["homogeneity"] += float((matrix / (1.0 + np.abs(i_idx - j_idx))).sum())
        accumulated["energy"] += float(np.sqrt((matrix**2).sum()))
        accumulated["correlation"] += (
            float(((i_idx - mean) * (j_idx - mean) * matrix).sum()) / variance if variance > 1e-12 else 1.0
        )
        accumulated["entropy"] += float(-(nonzero * np.log2(nonzero)).sum())
        used += 1

    return {name: (value / used if used else 0.0) for name, value in accumulated.items()}


def texture_features(gray: np.ndarray, region: np.ndarray, levels: int = 32) -> dict[str, float]:
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return {
        **glcm_features(gray, region, levels),
        "laplacian_variance": float(laplacian[region].var()) if region.any() else 0.0,
    }


# ---------- Bordes ----------


def edge_features(gray: np.ndarray, region: np.ndarray, roi_is_lesion: bool) -> dict[str, float | None]:
    """Densidad de bordes (Canny) dentro de la lesión y nitidez de su contorno (gradiente de Sobel)."""
    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    median = float(np.median(blurred[region])) if region.any() else 0.0
    lower = int(max(0.0, 0.66 * median))
    upper = int(min(255.0, 1.33 * median))
    if upper <= lower:
        upper = min(255, lower + 1)
    edges = cv2.Canny(blurred, lower, upper) > 0

    grad_x = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = np.hypot(grad_x, grad_y)

    area = int(region.sum())
    border_gradient: float | None = None
    if roi_is_lesion and area:
        eroded = cv2.erode(region.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        boundary = region & ~eroded
        border_gradient = float(magnitude[boundary].mean()) if boundary.any() else 0.0

    return {
        "edge_density": float((edges & region).sum() / area) if area else 0.0,
        "gradient_mean": float(magnitude[region].mean()) if area else 0.0,
        "border_gradient_mean": border_gradient,
    }


# ---------- Forma ----------


def shape_features(roi: np.ndarray) -> dict[str, float]:
    """Área relativa, circularidad, solidez, excentricidad y relación de aspecto del contorno principal."""
    mask = roi.astype(np.uint8)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contour = max(contours, key=cv2.contourArea)
    area = float(cv2.contourArea(contour))
    perimeter = float(cv2.arcLength(contour, True))
    hull_area = float(cv2.contourArea(cv2.convexHull(contour)))

    moments = cv2.moments(mask, binaryImage=True)
    eccentricity = 0.0
    if moments["m00"] > 0:
        mu20 = moments["mu20"] / moments["m00"]
        mu02 = moments["mu02"] / moments["m00"]
        mu11 = moments["mu11"] / moments["m00"]
        spread = np.sqrt(4 * mu11**2 + (mu20 - mu02) ** 2)
        major = (mu20 + mu02 + spread) / 2
        minor = (mu20 + mu02 - spread) / 2
        eccentricity = float(np.sqrt(max(0.0, 1 - minor / major))) if major > 0 else 0.0

    (_, (side_a, side_b), _) = cv2.minAreaRect(contour)
    short, long = sorted((side_a, side_b))

    return {
        "area_ratio": float(roi.mean()),
        "perimeter_px": perimeter,
        "circularity": float(min(1.0, 4 * np.pi * area / perimeter**2)) if perimeter > 0 else 0.0,
        "solidity": float(area / hull_area) if hull_area > 0 else 0.0,
        "eccentricity": eccentricity,
        "aspect_ratio": float(long / short) if short > 0 else 0.0,
    }


# ---------- Calidad ----------


def quality_features(lab: np.ndarray, gray: np.ndarray, glare: np.ndarray) -> dict[str, float]:
    return {
        "lightness_mean": float(lab[..., 0].mean()),
        "lightness_std": float(lab[..., 0].std()),
        "sharpness": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "glare_ratio": float(glare.mean()),
    }
