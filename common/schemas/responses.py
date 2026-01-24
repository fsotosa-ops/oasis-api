from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class OasisResponse(BaseModel, Generic[T]):
    """
    Envelope estándar para todas las respuestas de la API.
    """

    success: bool = Field(..., description="Indica si la operación fue exitosa.")
    message: str | None = Field(None, description="Mensaje legible para humanos.")
    data: T | None = Field(None, description="Payload de la respuesta.")
    meta: dict[str, Any] | None = Field(
        None, description="Metadatos (paginación, trace_id, etc)."
    )


class ErrorDetail(BaseModel):
    code: str
    message: str


class OasisErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
