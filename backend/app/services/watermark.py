"""Aviso incrustado en las imágenes procesadas.

La imagen procesada puede descargarse y compartirse fuera de la aplicación; la franja inferior
mantiene el aviso de uso no diagnóstico junto al resultado. No cambia el tamaño de la imagen.
"""

import numpy as np
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

STAMP_TEXTS = (
    "DermAI · resultado experimental, no es un diagnóstico médico",
    "DermAI · experimental, no diagnóstico",
    "No diagnóstico",
)


def stamp_disclaimer(image_bgr: np.ndarray) -> np.ndarray:
    """Oscurece una franja inferior y escribe el aviso más largo que quepa."""
    height, width = image_bgr.shape[:2]
    band = max(14, round(height * 0.06))
    output = image_bgr.copy()
    output[height - band :] = (output[height - band :].astype(np.float32) * 0.3).astype(np.uint8)

    canvas = PILImage.fromarray(np.ascontiguousarray(output[..., ::-1]))  # BGR -> RGB
    draw = ImageDraw.Draw(canvas)
    font_size = max(9, round(band * 0.6))
    font = ImageFont.load_default(size=font_size)
    text = next((t for t in STAMP_TEXTS if draw.textlength(t, font=font) <= width - 12), STAMP_TEXTS[-1])
    draw.text((6, height - band + (band - font_size) / 2 - 1), text, fill=(255, 255, 255), font=font)
    return np.asarray(canvas)[..., ::-1].copy()
