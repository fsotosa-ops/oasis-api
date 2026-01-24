from datetime import datetime
from typing import Any, Literal

from pydantic import UUID4, BaseModel, Field

# Ahora incluye los tipos sociales y de recursos
StepType = Literal[
    "survey",
    "event_attendance",
    "content_view",
    "milestone",
    "social_interaction",
    "resource_consumption",
]


class GamificationRules(BaseModel):
    points_base: int = 0
    bonus_rules: dict[str, Any] | None = Field(
        default=None, description="Reglas extra ej: {'min_duration': 60, 'bonus': 5}"
    )


class StepBase(BaseModel):
    title: str
    type: StepType
    gamification_rules: GamificationRules = Field(default_factory=GamificationRules)
    config: dict[str, Any] = Field(default_factory=dict)


class StepRead(StepBase):
    id: UUID4
    journey_id: UUID4


class JourneyBase(BaseModel):
    title: str
    slug: str
    description: str | None = None
    is_active: bool = True
    metadata: dict = Field(default_factory=dict)


class JourneyRead(JourneyBase):
    id: UUID4
    organization_id: UUID4
    created_at: datetime
    steps: list[StepRead] = []

    class Config:
        from_attributes = True
