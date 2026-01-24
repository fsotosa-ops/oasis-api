# common/exceptions.py
"""
Centralized exception handling for all OASIS services.

Usage:
    from common.exceptions import NotFoundError, ConflictError, oasis_exception_handler

    # In main.py:
    app.add_exception_handler(OasisException, oasis_exception_handler)

    # In endpoints:
    raise NotFoundError("journey", journey_id)
    raise ConflictError(ErrorCodes.ENROLLMENT_ALREADY_EXISTS, "Ya inscrito")
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse

from common.errors import ErrorCodes
from common.schemas.responses import ErrorDetail, OasisErrorResponse


class OasisException(Exception):
    """Base exception for all OASIS services."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(OasisException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str = ""):
        detail = (
            f"{resource} no encontrado"
            if not identifier
            else f"{resource} con id {identifier} no encontrado"
        )
        super().__init__(
            code=f"{resource.lower()}_not_found",
            message=detail,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(OasisException):
    """Resource conflict (duplicate, already exists, etc.)."""

    def __init__(self, code: str, message: str):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
        )


class UnauthorizedError(OasisException):
    """Authentication required or invalid."""

    def __init__(self, message: str = "No autorizado"):
        super().__init__(
            code=ErrorCodes.UNAUTHORIZED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(OasisException):
    """Authenticated but not allowed."""

    def __init__(self, message: str = "No tienes permisos para esta acción"):
        super().__init__(
            code="forbidden",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationError(OasisException):
    """Business logic validation failed."""

    def __init__(self, code: str, message: str):
        super().__init__(
            code=code,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class InternalError(OasisException):
    """Unexpected server error."""

    def __init__(self, message: str = "Error interno del servidor"):
        super().__init__(
            code=ErrorCodes.INTERNAL_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# =============================================================================
# Exception Handler
# =============================================================================


async def oasis_exception_handler(
    request: Request, exc: OasisException
) -> JSONResponse:
    """
    Global exception handler for OasisException.

    Register in FastAPI:
        app.add_exception_handler(OasisException, oasis_exception_handler)
    """
    return JSONResponse(
        status_code=exc.status_code,
        content=OasisErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message)
        ).model_dump(),
    )
