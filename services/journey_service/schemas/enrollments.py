from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, Field


class EnrollmentCreate(BaseModel):
    """Payload para inscribirse en un journey. user_id se obtiene del token JWT."""

    journey_id: UUID4 = Field(..., description="ID del Journey a iniciar.")
    metadata: dict | None = Field(default_factory=dict)


class EnrollmentResponse(BaseModel):
    """Respuesta básica de inscripción."""

    id: UUID4
    user_id: UUID4
    journey_id: UUID4
    status: str = Field(..., example="active")
    current_step_index: int
    progress_percentage: float
    started_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class StepProgressRead(BaseModel):
    """Progreso de un step individual."""

    step_id: UUID4
    title: str
    type: str
    order_index: int
    status: Literal["locked", "available", "completed"]
    completed_at: datetime | None = None
    points_earned: int = 0


class StepCompletionOut(BaseModel):
    """Detalle de un step completado."""

    id: UUID4
    step_id: UUID4
    step_title: str
    step_type: str
    completed_at: datetime
    points_earned: int
    metadata: dict = Field(default_factory=dict)


class JourneyBasicInfo(BaseModel):
    """Información básica del journey para incluir en enrollment."""

    id: UUID4
    title: str
    slug: str
    description: str | None = None
    thumbnail_url: str | None = None
    total_steps: int = 0


class EnrollmentDetailResponse(BaseModel):
    """Respuesta detallada de inscripción con journey y progreso."""

    id: UUID4
    user_id: UUID4
    journey_id: UUID4
    status: str
    current_step_index: int
    progress_percentage: float
    started_at: datetime
    completed_at: datetime | None = None

    # Información del journey
    journey: JourneyBasicInfo | None = None

    # Progreso detallado
    steps_progress: list[StepProgressRead] = Field(default_factory=list)
    completed_steps: int = 0
    total_steps: int = 0

    class Config:
        from_attributes = True
