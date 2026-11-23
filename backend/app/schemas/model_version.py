import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ModelVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    version: str
    architecture: str | None
    description: str | None
    metrics: dict[str, Any] | None
    is_active: bool
    created_at: datetime
