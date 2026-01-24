from datetime import datetime

from pydantic import UUID4, BaseModel, Field


class LevelInfo(BaseModel):
    """Información de un nivel."""

    id: UUID4
    name: str
    min_points: int
    icon_url: str | None = None
    benefits: dict | None = None


class UserStats(BaseModel):
    """Estadísticas completas del usuario."""

    user_id: UUID4
    total_points: int = 0
    current_level: LevelInfo | None = None
    next_level: LevelInfo | None = None
    points_to_next_level: int | None = None
    active_enrollments: int = 0
    completed_journeys: int = 0
    total_activities: int = 0


class LeaderboardEntry(BaseModel):
    """Entrada en el ranking."""

    rank: int
    user_id: UUID4
    full_name: str
    avatar_url: str | None = None
    total_points: int
    level_name: str | None = None


class RewardOut(BaseModel):
    """Recompensa/insignia obtenida."""

    id: UUID4
    reward_id: UUID4
    name: str
    description: str | None = None
    type: str  # 'badge' or 'points'
    icon_url: str | None = None
    earned_at: datetime
    journey_id: UUID4 | None = None


class ActivityLogEntry(BaseModel):
    """Entrada en el historial de actividades."""

    id: UUID4
    type: str
    points_awarded: int
    created_at: datetime
    metadata: dict = Field(default_factory=dict)


class PointsHistoryEntry(BaseModel):
    """Entrada en el historial de puntos."""

    id: UUID4
    amount: int
    reason: str
    created_at: datetime
    reference_id: UUID4 | None = None
