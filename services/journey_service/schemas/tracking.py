from typing import Any

from pydantic import UUID4, BaseModel, Field


class ActivityTrack(BaseModel):
    """Payload para registrar actividad. user_id se obtiene del token JWT."""

    activity_type: str = Field(..., description="Ej: 'social_post', 'video_view'")

    # Contexto opcional para vincularlo a un Journey específico
    journey_id: UUID4 | None = None
    step_id: UUID4 | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)


class ActivityResponse(BaseModel):
    """Respuesta del tracking de actividad."""

    points_earned: int = Field(..., description="Puntos ganados por esta actividad.")
    new_total: int | None = Field(
        None, description="Total de puntos del usuario (si aplica)."
    )
    level_up: bool = Field(
        default=False, description="True si el usuario subió de nivel."
    )
