"""
Conexión a la base de datos y gestión de sesiones (SQLAlchemy 2.0).

El engine se crea de forma perezosa: la aplicación puede arrancar (p. ej. el
endpoint /health) aunque DATABASE_URL no esté configurada todavía.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL no está configurada. Copia .env.example como .env "
            "en la raíz del proyecto y ajusta la URL de PostgreSQL."
        )
    return make_engine(settings.database_url, echo=settings.db_echo)


def make_engine(url: str, echo: bool = False) -> Engine:
    """Engine de PostgreSQL (desarrollo) o SQLite (demo desplegada, sin servidor de base de datos)."""
    if not url.startswith("sqlite"):
        return create_engine(url, echo=echo, pool_pre_ping=True)

    # FastAPI usa varios hilos; SQLite necesita permitirlo y activar las claves foráneas.
    engine = create_engine(url, echo=echo, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record) -> None:  # pragma: no cover - lo invoca SQLAlchemy
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión por petición y la cierra al terminar."""
    with get_sessionmaker()() as session:
        yield session
