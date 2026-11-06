"""Dependencias compartidas de los endpoints."""

import re
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import BadRequestError, TooManyRequestsError
from app.services.demo import RateLimiter
from app.services.storage import LocalStorage

SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSession = Annotated[Session, Depends(get_db)]


def get_storage(settings: SettingsDep) -> LocalStorage:
    return LocalStorage(settings.storage_dir)


StorageDep = Annotated[LocalStorage, Depends(get_storage)]

Limit = Annotated[int, Query(ge=1, le=100, description="Número máximo de elementos")]
Offset = Annotated[int, Query(ge=0, description="Elementos a omitir")]


# ---------- Modo demo ----------

SESSION_HEADER = "X-DermAI-Session"
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9-]{16,64}$")


def get_session_id(
    settings: SettingsDep,
    header_session: Annotated[str | None, Header(alias=SESSION_HEADER, include_in_schema=False)] = None,
    session: Annotated[
        str | None,
        Query(description="Solo en modo demo: identificador de sesión (para <img src>, que no envía cabeceras)"),
    ] = None,
) -> str | None:
    """En modo demo, identifica el navegador para que cada visitante solo vea sus imágenes.

    Fuera del modo demo devuelve None y no se filtra nada.
    """
    if not settings.demo_mode:
        return None
    value = header_session or session
    if not value or not SESSION_PATTERN.fullmatch(value):
        raise BadRequestError("Falta un identificador de sesión válido (modo demo).")
    return value


SessionId = Annotated[str | None, Depends(get_session_id)]


@lru_cache
def get_rate_limiter(limit: int) -> RateLimiter:
    return RateLimiter(limit)


def enforce_rate_limit(request: Request, settings: SettingsDep) -> None:
    """En modo demo, limita subidas y análisis por dirección IP."""
    if not settings.demo_mode:
        return
    client = request.client.host if request.client else "desconocido"
    if not get_rate_limiter(settings.demo_rate_limit_per_hour).hit(client):
        raise TooManyRequestsError(
            "Has alcanzado el límite de la demo "
            f"({settings.demo_rate_limit_per_hour} operaciones por hora). Vuelve a intentarlo más tarde."
        )


RateLimited = Depends(enforce_rate_limit)
