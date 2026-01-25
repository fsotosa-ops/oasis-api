"""Journey Service API endpoints."""

from services.journey_service.api.v1.endpoints import (
    admin_analytics,
    admin_gamification,
    admin_journeys,
    enrollments,
    gamification,
    journeys,
    tracking,
)

__all__ = [
    "admin_analytics",
    "admin_gamification",
    "admin_journeys",
    "enrollments",
    "gamification",
    "journeys",
    "tracking",
]
