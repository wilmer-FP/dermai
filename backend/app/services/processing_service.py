"""Ejecución del análisis: heurística de OpenCV (ai/preprocessing) o modelo entrenado (ai/models)."""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT
from app.models import Analysis, AnalysisStatus, ModelVersion
from app.services.storage import LocalStorage
from app.services.watermark import stamp_disclaimer

# El módulo `ai` vive en la raíz del repositorio, fuera de `backend/`.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from ai.preprocessing import AnalysisOutput, ImageDecodeError, analyze_image_bytes, encode_png  # noqa: E402

logger = logging.getLogger("dermai")

PROCESSING_ERROR = "No se pudo procesar la imagen."


class ModelUnavailableError(RuntimeError):
    """El modelo no se puede usar (PyTorch no instalado, pesos ausentes o dañados)."""


def processed_filename(analysis: Analysis) -> str:
    return f"{analysis.id.hex}_processed.png"


def resolve_weights_path(model_version: ModelVersion) -> Path:
    if not model_version.weights_path:
        raise ModelUnavailableError("La versión de modelo no tiene archivo de pesos.")
    path = Path(model_version.weights_path)
    path = path if path.is_absolute() else PROJECT_ROOT / path
    if not path.is_file():
        raise ModelUnavailableError("No se encuentra el archivo de pesos del modelo.")
    return path


def analyze_with_model_version(data: bytes, model_version: ModelVersion, device: str) -> AnalysisOutput:
    weights = resolve_weights_path(model_version)
    try:
        from ai.models.inference import analyze_bytes_with_model, load_model_cached
    except ImportError as exc:  # PyTorch no instalado en este entorno
        raise ModelUnavailableError("PyTorch no está instalado en el servidor.") from exc
    try:
        loaded = load_model_cached(weights, device)
    except Exception as exc:
        raise ModelUnavailableError("No se pudo cargar el modelo.") from exc
    return analyze_bytes_with_model(data, loaded)


def run_analysis(db: Session, storage: LocalStorage, analysis: Analysis, device: str = "cpu") -> Analysis:
    """Procesa la imagen del análisis y guarda métricas, características y visualización.

    Sin versión de modelo se usa la heurística (sin confianza); con versión de modelo, la
    inferencia de PyTorch (con confianza no calibrada). El estado pasa a `processing` y
    después a `completed` o `failed`.
    """
    analysis.status = AnalysisStatus.PROCESSING
    db.commit()

    try:
        data = storage.path_for(analysis.image.stored_filename).read_bytes()
        if analysis.model_version is not None:
            output = analyze_with_model_version(data, analysis.model_version, device)
        else:
            output = analyze_image_bytes(data)
        filename = processed_filename(analysis)
        storage.save(filename, encode_png(stamp_disclaimer(output.overlay)))
    except ModelUnavailableError as exc:
        logger.warning("Análisis %s fallido: %s", analysis.id, exc)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = f"{PROCESSING_ERROR} {exc}"
    except (ImageDecodeError, OSError, ValueError) as exc:
        logger.warning("Análisis %s fallido: %s", analysis.id, exc)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = f"{PROCESSING_ERROR} {exc}".strip()
    except Exception:
        logger.exception("Error inesperado procesando el análisis %s", analysis.id)
        analysis.status = AnalysisStatus.FAILED
        analysis.error_message = PROCESSING_ERROR
    else:
        analysis.status = AnalysisStatus.COMPLETED
        analysis.necrotic_area_ratio = output.necrotic_area_ratio
        analysis.confidence = output.confidence
        analysis.result = output.result
        analysis.processed_image_filename = filename
        logger.info(
            "Análisis %s completado con %s (área compatible con necrosis: %.4f)",
            analysis.id,
            output.result.get("method", {}).get("name"),
            output.necrotic_area_ratio,
        )

    analysis.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(analysis)
    return analysis
