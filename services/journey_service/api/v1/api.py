from fastapi import APIRouter

from services.journey_service.api.v1.endpoints import (
    enrollments,
    gamification,
    journeys,
    tracking,
)

api_router = APIRouter()

# Journeys - Rutas de experiencia
api_router.include_router(
    journeys.router,
    prefix="/journeys",
    tags=["Journeys"],
)

# Enrollments - Inscripciones
api_router.include_router(
    enrollments.router,
    prefix="/enrollments",
    tags=["Enrollments"],
)

# Tracking - Registro de actividades
api_router.include_router(
    tracking.router,
    prefix="/tracking",
    tags=["Tracking"],
)

# Gamification - Estadísticas, puntos, niveles
api_router.include_router(
    gamification.router,
    prefix="/me",
    tags=["Gamification"],
)
