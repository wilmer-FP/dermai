"""Router principal: agrupa los routers de cada módulo de la API."""

from fastapi import APIRouter

from app.api.routes import analyses, health, images, model_versions

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(images.router)
api_router.include_router(analyses.router)
api_router.include_router(model_versions.router)
