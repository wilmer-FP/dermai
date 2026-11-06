"""
Modelos ORM de DermAI.

Importar todos los modelos aquí garantiza que queden registrados en
`Base.metadata` (lo necesita Alembic para comparar el esquema).
"""

from app.models.analysis import Analysis, AnalysisStatus
from app.models.base import Base
from app.models.image import Image
from app.models.model_version import ModelVersion

__all__ = ["Analysis", "AnalysisStatus", "Base", "Image", "ModelVersion"]
