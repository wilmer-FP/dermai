from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    version: str
    environment: str
    demo_mode: bool = False
    # Horas tras las que se borran las imágenes en modo demo (None fuera del modo demo)
    demo_retention_hours: float | None = None
