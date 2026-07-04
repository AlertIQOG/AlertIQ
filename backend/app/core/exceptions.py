"""
Domain-level exceptions for the AlertIQ backend.

These are raised by the service layer and mapped to HTTP responses
by the exception handlers registered on the FastAPI app.
Services should NEVER import or raise HTTPException directly.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base exception for all domain errors."""

    def __init__(self, detail: str = "An unexpected error occurred"):
        self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} ({identifier}) not found"
        super().__init__(detail)


class ConflictError(AppException):
    """Raised when a create/update would violate a uniqueness constraint."""

    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(detail)


class NotificationError(AppException):
    """Raised when an outbound notification channel fails to deliver.

    Caught in-band by the notification dispatcher (reported as a per-channel
    result), so it has no HTTP handler.
    """

    def __init__(self, detail: str = "Failed to send notification"):
        super().__init__(detail)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach domain-exception → HTTP-response mappings to the app."""

    @app.exception_handler(NotFoundError)
    async def _not_found(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    @app.exception_handler(ConflictError)
    async def _conflict(request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.detail})
