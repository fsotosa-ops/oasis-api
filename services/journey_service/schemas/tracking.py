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


class ExternalEventPayload(BaseModel):
    """
    Normalized event payload from webhook_service.

    This is the standard format for events coming from external sources
    (Typeform, Stripe, etc.) via the webhook service.
    """

    # Event identification
    source: str = Field(..., description="Provider name (e.g., 'typeform', 'stripe')")
    event_type: str = Field(..., description="Type of event (e.g., 'form_submission')")
    external_id: str | None = Field(None, description="Provider's event ID")
    resource_id: str | None = Field(None, description="Resource ID (form_id, etc.)")
    occurred_at: str | None = Field(None, description="ISO timestamp of event")

    # User identification
    user_identifier: str | None = Field(
        None, description="User ID, email, or other identifier"
    )
    organization_id: str | None = Field(None, description="Organization context")

    # Additional data
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (enrollment_id, journey_id, step_id, etc.)",
    )


class ExternalEventResponse(BaseModel):
    """Response for external event processing."""

    processed: bool = Field(..., description="Whether the event was processed")
    message: str = Field(..., description="Processing result message")
    points_earned: int = Field(default=0, description="Points awarded, if any")
    step_completed: bool = Field(
        default=False, description="Whether a step was completed"
    )
