from typing import Annotated

from fastapi import APIRouter, Depends

from app import __version__
from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Estado del servicio")
def health_check(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Comprueba que la API está en ejecución."""
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        demo_mode=settings.demo_mode,
        demo_retention_hours=settings.demo_retention_hours if settings.demo_mode else None,
    )
