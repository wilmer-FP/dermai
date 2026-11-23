"""Pipeline completo: preprocesamiento, segmentación, clasificación de tejido y características.

Es un método heurístico clásico (sin aprendizaje automático). Sus resultados describen
propiedades visuales de la imagen y NO constituyen un diagnóstico médico.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from . import enhancement, features, segmentation, tissue, visualization
from .config import PipelineConfig
from .io import decode_image

METHOD_NAME = "dermai-opencv-heuristic"
METHOD_VERSION = "0.1.0"
METHOD_DESCRIPTION = (
    "Segmentación por diferencia de color con la piel circundante y clasificación de "
    "tejido por umbrales en CIELAB. Método heurístico sin validación clínica."
)


@dataclass(frozen=True)
class PreprocessedImage:
    resized: np.ndarray  # BGR original escalada (base de la visualización)
    corrected: np.ndarray  # con constancia de color
    denoised: np.ndarray  # corregida y filtrada (segmentación y color)
    lab: np.ndarray
    gray: np.ndarray  # de la imagen corregida sin filtrar (textura)
    glare: np.ndarray


@dataclass(frozen=True)
class AnalysisOutput:
    necrotic_area_ratio: float
    result: dict[str, Any]
    overlay: np.ndarray
    roi_mask: np.ndarray
    tissue_labels: np.ndarray
    # Solo los modelos producen una confianza; la heurística la deja vacía.
    confidence: float | None = None


def preprocess(image: np.ndarray, config: PipelineConfig) -> PreprocessedImage:
    """Redimensionado, constancia de color, reducción de ruido y conversión a CIELAB."""
    resized = enhancement.resize_longest_side(image, config.target_size)
    glare = segmentation.detect_glare(resized, config)
    corrected = enhancement.shades_of_gray(
        resized, config.shades_of_gray_power, mask=~glare, strength=config.color_constancy_strength
    )
    denoised = enhancement.denoise(
        corrected, config.bilateral_diameter, config.bilateral_sigma_color, config.bilateral_sigma_space
    )
    return PreprocessedImage(
        resized=resized,
        corrected=corrected,
        denoised=denoised,
        lab=enhancement.to_lab(denoised),
        gray=enhancement.to_gray(corrected),
        glare=glare,
    )


def _round(value: Any, digits: int = 4) -> Any:
    """Redondea y convierte a tipos de Python para que el resultado sea JSON serializable."""
    if isinstance(value, dict):
        return {key: _round(item, digits) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(item, digits) for item in value]
    if isinstance(value, (float, np.floating)):
        return round(float(value), digits)
    if isinstance(value, np.integer):
        return int(value)
    return value


def quality_warnings(original_shape: tuple[int, ...], quality: dict[str, float]) -> list[str]:
    """Avisos sobre la calidad de la foto (resolución, enfoque, exposición, reflejos)."""
    messages: list[str] = []
    if min(original_shape[:2]) < 200:
        messages.append("Resolución baja (menos de 200 px); los resultados son menos fiables.")
    if quality["sharpness"] < 20:
        messages.append("La imagen parece desenfocada.")
    if quality["lightness_mean"] < 25:
        messages.append("La imagen es muy oscura.")
    elif quality["lightness_mean"] > 90:
        messages.append("La imagen parece sobreexpuesta.")
    if quality["glare_ratio"] > 0.05:
        messages.append("Hay reflejos de luz; esos píxeles se excluyeron del análisis.")
    return messages


def _warnings(
    original_shape: tuple[int, ...], seg: segmentation.Segmentation, quality: dict[str, float]
) -> list[str]:
    messages: list[str] = []
    if seg.fallback:
        messages.append("No se distinguió una lesión del fondo; se analizó la imagen completa.")
    elif seg.border_contact > 0.25:
        messages.append(
            "La lesión llega a los bordes de la imagen; la referencia de piel sana puede no ser fiable."
        )
    return messages + quality_warnings(original_shape, quality)


def _hex(bgr: tuple[int, int, int]) -> str:
    blue, green, red = bgr
    return f"#{red:02x}{green:02x}{blue:02x}"


HEURISTIC_LEGEND = [
    {"label": "Región analizada", "color": _hex(visualization.ROI_COLOR), "kind": "outline"},
    {"label": "Negro / marrón oscuro", "color": _hex(visualization.OVERLAY_COLORS[tissue.NECROTIC][0]), "kind": "fill"},
    {"label": "Amarillo", "color": _hex(visualization.OVERLAY_COLORS[tissue.SLOUGH][0]), "kind": "fill"},
]


def analyze_image(image: np.ndarray, config: PipelineConfig | None = None) -> AnalysisOutput:
    """Analiza una imagen BGR (uint8, 3 canales) y devuelve métricas, características y visualización."""
    config = config or PipelineConfig()
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("Se esperaba una imagen BGR de 8 bits y 3 canales.")

    pre = preprocess(image, config)
    valid = ~pre.glare
    seg = segmentation.segment_lesion(pre.lab, valid, config)
    region = seg.mask & valid
    if not region.any():  # región cubierta por reflejos: se usa la región sin excluir nada
        region = seg.mask

    tissue_map = tissue.classify_tissue(pre.lab, region, seg.skin_reference_lab, config.tissue)
    quality = features.quality_features(pre.lab, pre.gray, pre.glare)

    result = {
        "method": {"name": METHOD_NAME, "version": METHOD_VERSION, "description": METHOD_DESCRIPTION},
        "preprocessing": {
            "original_size": [int(image.shape[1]), int(image.shape[0])],
            "processed_size": [int(pre.resized.shape[1]), int(pre.resized.shape[0])],
            "color_constancy": (
                f"shades_of_gray(p={config.shades_of_gray_power:g}, "
                f"strength={config.color_constancy_strength:g})"
            ),
            "denoising": "bilateral",
        },
        "segmentation": {
            "roi_area_ratio": float(seg.mask.mean()),
            "fallback_full_image": seg.fallback,
            "border_contact": seg.border_contact,
            "threshold_delta_e": seg.threshold_delta_e,
        },
        "tissue_composition": tissue_map.ratios,
        "color": features.color_features(pre.lab, region, seg.skin_reference_lab),
        "texture": features.texture_features(pre.gray, region, config.glcm_levels),
        "edges": features.edge_features(pre.gray, region, roi_is_lesion=not seg.fallback),
        "shape": None if seg.fallback else features.shape_features(seg.mask),
        "quality": quality,
        "warnings": _warnings(image.shape, seg, quality),
        "legend": HEURISTIC_LEGEND,
        "config": config.to_dict(),
    }

    overlay = visualization.render_overlay(pre.resized, seg.mask, tissue_map.labels, draw_roi=not seg.fallback)
    return AnalysisOutput(
        necrotic_area_ratio=round(tissue_map.ratios["necrotic"], 4),
        result=_round(result),
        overlay=overlay,
        roi_mask=seg.mask,
        tissue_labels=tissue_map.labels,
    )


def analyze_image_bytes(data: bytes, config: PipelineConfig | None = None) -> AnalysisOutput:
    return analyze_image(decode_image(data), config)
