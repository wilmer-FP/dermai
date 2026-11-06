"""Parámetros del pipeline de preprocesamiento.

Todos los umbrales son heurísticos: se eligieron para un prototipo educativo y NO están
validados clínicamente. Se agrupan aquí para que cada experimento pueda registrar y
reproducir exactamente la configuración usada.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TissueThresholds:
    """Umbrales en CIELAB (L* 0–100, a*/b* aprox. −128–127, tono en grados).

    Siguen el esquema clásico de color de heridas (negro / amarillo / rojo):
    - Necrótico: muy oscuro en términos absolutos Y bastante más oscuro que la piel de
      referencia, con poca saturación. La condición relativa evita que una piel de
      fototipo oscuro se clasifique entera como "necrótica".
    - Esfacelo: claro, de tono amarillo y más amarillo que la piel de referencia.
    - Granulación: tono rojo y más rojo que la piel de referencia.
    """

    necrotic_max_lightness: float = 40.0
    necrotic_min_darkening: float = 25.0
    necrotic_max_chroma: float = 35.0
    slough_min_lightness: float = 50.0
    slough_hue_range: tuple[float, float] = (50.0, 115.0)
    slough_min_b: float = 18.0
    slough_min_b_over_skin: float = 8.0
    granulation_hue_range: tuple[float, float] = (-30.0, 45.0)
    granulation_min_a: float = 15.0
    granulation_min_a_over_skin: float = 8.0


@dataclass(frozen=True)
class PipelineConfig:
    # Normalización de tamaño: lado mayor fijo para que las medidas sean comparables.
    target_size: int = 512
    # Constancia de color "Shades of Gray" (norma de Minkowski de orden p).
    shades_of_gray_power: float = 6.0
    # Fuerza de la corrección (0 = ninguna, 1 = completa). En fotos dominadas por piel, la
    # corrección completa vuelve gris la propia piel y desplaza los tonos amarillos.
    color_constancy_strength: float = 0.5
    # Reducción de ruido con filtro bilateral (conserva bordes).
    bilateral_diameter: int = 7
    bilateral_sigma_color: float = 40.0
    bilateral_sigma_space: float = 7.0
    # Segmentación: franja del borde usada como referencia de piel sana.
    border_fraction: float = 0.08
    # Diferencia de color mínima (ΔE) para considerar que hay lesión.
    min_lesion_delta_e: float = 8.0
    # La región de interés debe ocupar entre estos porcentajes de la imagen.
    min_roi_ratio: float = 0.005
    max_roi_ratio: float = 0.95
    # Reflejos especulares: muy brillantes y casi sin saturación (escala HSV de OpenCV).
    glare_min_value: int = 235
    glare_max_saturation: int = 30
    # Niveles de gris de la matriz de co-ocurrencia (GLCM).
    glcm_levels: int = 32
    tissue: TissueThresholds = field(default_factory=TissueThresholds)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
