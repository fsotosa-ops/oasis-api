from fastapi import APIRouter

from services.journey_service.api.v1.endpoints import enrollments, tracking

api_router = APIRouter()

api_router.include_router(
    enrollments.router, prefix="/enrollments", tags=["Enrollments"]
)
api_router.include_router(
    tracking.router, prefix="/tracking", tags=["Gamification & Tracking"]
)
