"""
DermAI - Punto de entrada del backend (FastAPI).

Ejecución en desarrollo (desde la carpeta backend/):
    .venv\\Scripts\\python -m uvicorn app.main:app --reload

Aviso: DermAI es un prototipo experimental y educativo.
No es una herramienta de diagnóstico médico.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.constants import DISCLAIMER
from app.core.database import get_sessionmaker
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.services.demo import purge_expired_images
from app.services.storage import LocalStorage

logger = logging.getLogger("dermai")

PURGE_INTERVAL_SECONDS = 600


def purge_once(settings: Settings) -> int:
    with get_sessionmaker()() as db:
        return purge_expired_images(db, LocalStorage(settings.storage_dir), settings.demo_retention_hours)


async def purge_loop(settings: Settings) -> None:
    """Modo demo: borra periódicamente las imágenes caducadas."""
    while True:
        try:
            await run_in_threadpool(purge_once, settings)
        except Exception:
            logger.exception("Error al borrar imágenes caducadas")
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("Iniciando %s v%s (entorno: %s)", settings.app_name, __version__, settings.app_env)
        logger.info(DISCLAIMER)
        purge_task = None
        if settings.demo_mode:
            logger.info("Modo demo activo: las imágenes se borran a las %g h", settings.demo_retention_hours)
            purge_task = asyncio.create_task(purge_loop(settings))
        yield
        if purge_task is not None:
            purge_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await purge_task
        logger.info("Deteniendo %s", settings.app_name)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description=DISCLAIMER,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root(current: Annotated[Settings, Depends(get_settings)]) -> dict[str, str | bool | None]:
        """Página de entrada de la API (p. ej. al abrir el Space de Hugging Face)."""
        return {
            "app": f"{current.app_name} API",
            "version": __version__,
            "docs": "/docs",
            "health": f"{current.api_prefix}/health",
            "frontend": current.frontend_url,
            "demo_mode": current.demo_mode,
            "disclaimer": DISCLAIMER,
        }

    return app


app = create_app()
