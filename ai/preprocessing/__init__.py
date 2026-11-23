"""Preprocesamiento y extracción de características de imágenes de lesiones cutáneas (OpenCV).

Uso básico::

    from ai.preprocessing import analyze_image_bytes

    output = analyze_image_bytes(open("lesion.jpg", "rb").read())
    output.necrotic_area_ratio   # proporción 0–1 de la lesión con color compatible con necrosis
    output.result                # dict JSON con características, avisos y configuración
    output.overlay               # imagen BGR con la región y los tejidos marcados

Método heurístico y experimental: no es un diagnóstico médico.
"""

from .config import PipelineConfig, TissueThresholds
from .io import ImageDecodeError, decode_image, encode_png, load_image
from .pipeline import (
    METHOD_NAME,
    METHOD_VERSION,
    AnalysisOutput,
    PreprocessedImage,
    analyze_image,
    analyze_image_bytes,
    preprocess,
)

__all__ = [
    "METHOD_NAME",
    "METHOD_VERSION",
    "AnalysisOutput",
    "ImageDecodeError",
    "PipelineConfig",
    "PreprocessedImage",
    "TissueThresholds",
    "analyze_image",
    "analyze_image_bytes",
    "decode_image",
    "encode_png",
    "load_image",
    "preprocess",
]
