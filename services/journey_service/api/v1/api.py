from fastapi import APIRouter

from services.journey_service.api.v1.endpoints import (
    admin_analytics,
    admin_gamification,
    admin_journeys,
    enrollments,
    gamification,
    journeys,
    tracking,
)

api_router = APIRouter()

# =============================================================================
# USER ENDPOINTS (Public)
# =============================================================================

# Journeys - Rutas de experiencia (lectura)
api_router.include_router(
    journeys.router,
    prefix="/journeys",
    tags=["Journeys"],
)

# Enrollments - Inscripciones de usuarios
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

# Gamification - Estadísticas personales, puntos, niveles
api_router.include_router(
    gamification.router,
    prefix="/me",
    tags=["Gamification"],
)

# =============================================================================
# ADMIN ENDPOINTS (Backoffice)
# =============================================================================

# Admin Journeys - CRUD de journeys y steps
api_router.include_router(
    admin_journeys.router,
    prefix="/admin/journeys",
    tags=["Admin - Journeys"],
)

# Admin Gamification - Configuración de niveles y recompensas
api_router.include_router(
    admin_gamification.router,
    prefix="/admin",
    tags=["Admin - Gamification"],
)

# Admin Analytics - Reportes y estadísticas
api_router.include_router(
    admin_analytics.router,
    prefix="/admin",
    tags=["Admin - Analytics"],
)
