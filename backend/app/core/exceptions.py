"""Errores de dominio y su traducción a respuestas HTTP."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.database import DatabaseNotConfiguredError

logger = logging.getLogger("dermai")


class DermAIError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DermAIError):
    status_code = status.HTTP_404_NOT_FOUND


class InvalidImageError(DermAIError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY


class UnsupportedMediaTypeError(DermAIError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class PayloadTooLargeError(DermAIError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class BadRequestError(DermAIError):
    status_code = status.HTTP_400_BAD_REQUEST


class TooManyRequestsError(DermAIError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DermAIError)
    async def handle_dermai_error(_: Request, exc: DermAIError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(DatabaseNotConfiguredError)
    async def handle_db_not_configured(_: Request, exc: DatabaseNotConfiguredError) -> JSONResponse:
        logger.error("%s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "La base de datos no está configurada."},
        )
