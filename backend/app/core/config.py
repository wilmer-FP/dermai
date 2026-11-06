"""
Configuración de la aplicación a partir de variables de entorno.

Los valores se leen, por orden de prioridad, de:
1. Variables de entorno del sistema.
2. Archivo `.env` en la raíz del proyecto (ver `.env.example`).
3. Valores por defecto definidos aquí.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] = raíz del proyecto (dermai/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Entorno
    app_name: str = "DermAI"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Backend
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    api_prefix: str = "/api/v1"
    # Lista separada por comas, p. ej. "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173"

    # Base de datos (formato SQLAlchemy, p. ej. postgresql+psycopg://usuario:clave@host:5432/bd)
    database_url: str | None = None
    db_echo: bool = False

    # Almacenamiento de imágenes (rutas relativas se resuelven desde la raíz del proyecto)
    storage_path: Path = Path("./storage")
    max_upload_size_mb: int = Field(default=10, gt=0)
    # Lista separada por comas, p. ej. "jpg,jpeg,png"
    allowed_image_extensions: str = "jpg,jpeg,png"

    # Inteligencia artificial: dispositivo de inferencia de los modelos (cpu, cuda o auto)
    ai_device: Literal["cpu", "cuda", "auto"] = "cpu"

    # Modo demo (despliegue público): cada visitante solo ve sus imágenes, que se borran
    # solas pasado `demo_retention_hours`, y se limita el número de subidas y análisis.
    demo_mode: bool = False
    demo_retention_hours: float = Field(default=6, gt=0)
    demo_rate_limit_per_hour: int = Field(default=30, gt=0)
    # URL pública del frontend (se muestra en la raíz de la API)
    frontend_url: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def storage_dir(self) -> Path:
        path = self.storage_path
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_extensions(self) -> set[str]:
        return {
            ext.strip().lower().lstrip(".")
            for ext in self.allowed_image_extensions.split(",")
            if ext.strip()
        }


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia única (cacheada) de la configuración."""
    return Settings()
