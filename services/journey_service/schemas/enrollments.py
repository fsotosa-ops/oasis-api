from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, Field


class EnrollmentCreate(BaseModel):
    """Payload para inscribirse en un journey. user_id se obtiene del token JWT."""

    journey_id: UUID4 = Field(..., description="ID del Journey a iniciar.")
    metadata: dict | None = Field(default_factory=dict)


class StepProgressRead(BaseModel):
    step_id: UUID4
    completed_at: datetime | None
    status: Literal["locked", "available", "completed"]


class EnrollmentResponse(BaseModel):
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
