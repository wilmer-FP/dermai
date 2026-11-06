"""Imagen de resultado: región de interés y tejidos coloreados sobre la fotografía."""

import cv2
import numpy as np

from .tissue import NECROTIC, SLOUGH

# Colores en BGR. Se usan colores que no aparecen en la piel para que se distingan bien.
ROI_COLOR = (80, 220, 80)  # verde: contorno de la región analizada
OVERLAY_COLORS: dict[int, tuple[tuple[int, int, int], float]] = {
    NECROTIC: ((255, 0, 255), 0.55),  # magenta
    SLOUGH: ((0, 215, 255), 0.45),  # amarillo
}


def render_overlay(base: np.ndarray, roi: np.ndarray, labels: np.ndarray, draw_roi: bool = True) -> np.ndarray:
    output = base.astype(np.float32)
    for code, (color, alpha) in OVERLAY_COLORS.items():
        mask = labels == code
        output[mask] = output[mask] * (1 - alpha) + np.asarray(color, dtype=np.float32) * alpha
    output = output.astype(np.uint8)
    if draw_roi:
        contours, _ = cv2.findContours(roi.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(output, contours, -1, ROI_COLOR, 2, lineType=cv2.LINE_AA)
    return output
