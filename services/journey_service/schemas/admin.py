"""
Admin schemas for Journey Service backoffice operations.

These schemas are used by organization admins/owners to manage:
- Journeys and Steps
- Levels and Rewards
- Analytics and reporting
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import UUID4, BaseModel, Field

from services.journey_service.schemas.journeys import GamificationRules, StepType

# =============================================================================
# JOURNEY ADMIN SCHEMAS
# =============================================================================


class JourneyCreate(BaseModel):
    """Schema for creating a new journey."""

    title: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    thumbnail_url: str | None = None
    is_active: bool = False  # Start as draft
    metadata: dict[str, Any] = Field(default_factory=dict)


class JourneyUpdate(BaseModel):
    """Schema for updating a journey."""

    title: str | None = Field(None, min_length=1, max_length=200)
    slug: str | None = Field(
        None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$"
    )
    description: str | None = None
    thumbnail_url: str | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class JourneyAdminRead(BaseModel):
    """Extended journey info for admin views."""

    id: UUID4
    organization_id: UUID4
    title: str
    slug: str
    description: str | None = None
    thumbnail_url: str | None = None
    is_active: bool
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    # Admin stats
    total_steps: int = 0
    total_enrollments: int = 0
    active_enrollments: int = 0
    completed_enrollments: int = 0
    completion_rate: float = 0.0

    class Config:
        from_attributes = True


# =============================================================================
# STEP ADMIN SCHEMAS
# =============================================================================


class StepCreate(BaseModel):
    """Schema for creating a step within a journey."""

    title: str = Field(..., min_length=1, max_length=200)
    type: StepType
    order_index: int | None = None  # If None, append at the end
    config: dict[str, Any] = Field(default_factory=dict)
    gamification_rules: GamificationRules = Field(default_factory=GamificationRules)


class StepUpdate(BaseModel):
    """Schema for updating a step."""

    title: str | None = Field(None, min_length=1, max_length=200)
    type: StepType | None = None
    config: dict[str, Any] | None = None
    gamification_rules: GamificationRules | None = None


class StepAdminRead(BaseModel):
    """Extended step info for admin views."""

    id: UUID4
    journey_id: UUID4
    title: str
    type: StepType
    order_index: int
    config: dict = Field(default_factory=dict)
    gamification_rules: GamificationRules = Field(default_factory=GamificationRules)
    created_at: datetime
    updated_at: datetime

    # Admin stats
    total_completions: int = 0
    average_points: float = 0.0

    class Config:
        from_attributes = True


class StepReorderItem(BaseModel):
    """Single item for reordering steps."""

    step_id: UUID4
    new_index: int = Field(..., ge=0)


class StepReorderRequest(BaseModel):
    """Request to reorder steps in a journey."""

    steps: list[StepReorderItem] = Field(..., min_length=1)


# =============================================================================
# LEVEL ADMIN SCHEMAS
# =============================================================================


class LevelCreate(BaseModel):
    """Schema for creating a level."""

    name: str = Field(..., min_length=1, max_length=100)
    min_points: int = Field(..., ge=0)
    icon_url: str | None = None
    benefits: dict[str, Any] = Field(default_factory=dict)


class LevelUpdate(BaseModel):
    """Schema for updating a level."""

    name: str | None = Field(None, min_length=1, max_length=100)
    min_points: int | None = Field(None, ge=0)
    icon_url: str | None = None
    benefits: dict[str, Any] | None = None


class LevelAdminRead(BaseModel):
    """Level info for admin views."""

    id: UUID4
    organization_id: UUID4 | None
    name: str
    min_points: int
    icon_url: str | None = None
    benefits: dict = Field(default_factory=dict)
    created_at: datetime

    # Admin stats
    users_at_level: int = 0

    class Config:
        from_attributes = True


# =============================================================================
# REWARD ADMIN SCHEMAS
# =============================================================================

RewardType = Literal["badge", "points"]


class RewardCreate(BaseModel):
    """Schema for creating a reward/badge."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    type: RewardType = "badge"
    icon_url: str | None = None
    unlock_condition: dict[str, Any] = Field(default_factory=dict)


class RewardUpdate(BaseModel):
    """Schema for updating a reward."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    type: RewardType | None = None
    icon_url: str | None = None
    unlock_condition: dict[str, Any] | None = None


class RewardAdminRead(BaseModel):
    """Reward info for admin views."""

    id: UUID4
    organization_id: UUID4 | None
    name: str
    description: str | None = None
    type: str
    icon_url: str | None = None
    unlock_condition: dict = Field(default_factory=dict)

    # Admin stats
    times_awarded: int = 0

    class Config:
        from_attributes = True


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================


class JourneyStats(BaseModel):
    """Detailed statistics for a journey."""

    journey_id: UUID4
    title: str

    # Enrollment stats
    total_enrollments: int = 0
    active_enrollments: int = 0
    completed_enrollments: int = 0
    dropped_enrollments: int = 0
    completion_rate: float = 0.0
    drop_rate: float = 0.0

    # Progress stats
    average_progress: float = 0.0
    average_completion_time_days: float | None = None

    # Points stats
    total_points_awarded: int = 0
    average_points_per_user: float = 0.0

    # Step completion breakdown
    step_completion_rates: list[dict] = Field(default_factory=list)


class EnrollmentAdminRead(BaseModel):
    """Enrollment info for admin views."""

    id: UUID4
    journey_id: UUID4
    user_id: UUID4
    status: str
    current_step_index: int
    progress_percentage: float
    started_at: datetime
    completed_at: datetime | None = None

    # User info
    user_email: str | None = None
    user_full_name: str | None = None

    # Journey info
    journey_title: str | None = None

    class Config:
        from_attributes = True


class UserProgressSummary(BaseModel):
    """Summary of a user's progress for admin view."""

    user_id: UUID4
    email: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None

    # Points and level
    total_points: int = 0
    current_level: str | None = None

    # Journey progress
    active_journeys: int = 0
    completed_journeys: int = 0
    dropped_journeys: int = 0

    # Recent activity
    last_activity_at: datetime | None = None
    total_activities: int = 0


class OrgAnalyticsSummary(BaseModel):
    """Organization-wide analytics summary."""

    organization_id: UUID4

    # User stats
    total_users: int = 0
    active_users_30d: int = 0

    # Journey stats
    total_journeys: int = 0
    active_journeys: int = 0

    # Engagement stats
    total_enrollments: int = 0
    overall_completion_rate: float = 0.0
    total_points_awarded: int = 0

    # Top performers
    top_users: list[UserProgressSummary] = Field(default_factory=list)

    # Most popular journeys
    popular_journeys: list[dict] = Field(default_factory=list)
