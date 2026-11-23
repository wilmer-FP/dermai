"""Modo demo: límite de peticiones y borrado automático de imágenes antiguas."""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Image
from app.services import image_service
from app.services.storage import LocalStorage

logger = logging.getLogger("dermai")


class RateLimiter:
    """Ventana deslizante en memoria: como máximo `limit` eventos por clave en `window_seconds`.

    Suficiente para una demo con un solo proceso; no se comparte entre procesos.
    """

    def __init__(self, limit: int, window_seconds: float = 3600.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> bool:
        """Registra un evento; devuelve False si se supera el límite (y entonces no lo registra)."""
        now = time.monotonic() if now is None else now
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= self.window:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


def purge_expired_images(db: Session, storage: LocalStorage, retention_hours: float) -> int:
    """Borra las imágenes (con sus análisis y archivos) creadas hace más de `retention_hours`."""
    cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
    if db.get_bind().dialect.name == "sqlite":  # SQLite guarda las fechas sin zona horaria (en UTC)
        cutoff = cutoff.replace(tzinfo=None)
    expired = db.scalars(select(Image.id).where(Image.created_at < cutoff)).all()
    for image_id in expired:
        image_service.delete_image(db, storage, image_id)
    if expired:
        logger.info("Modo demo: %d imágenes caducadas eliminadas", len(expired))
    return len(expired)
