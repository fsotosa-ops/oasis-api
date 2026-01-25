"""
Admin endpoints for Analytics and Reporting.

View enrollment data, user progress, and organization-wide statistics.
Authorization: Requires 'owner' or 'admin' role in the organization.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from common.auth.security import OrgRoleChecker
from common.database.client import get_admin_client
from common.exceptions import NotFoundError
from common.schemas.responses import OasisResponse
from services.journey_service.crud import admin as crud
from services.journey_service.schemas.admin import (
    EnrollmentAdminRead,
    OrgAnalyticsSummary,
    UserProgressSummary,
)
from supabase import AsyncClient

router = APIRouter()

# Role checker for admin operations
AdminRequired = OrgRoleChecker(["owner", "admin"])


# =============================================================================
# ENROLLMENT ANALYTICS
# =============================================================================


@router.get(
    "/enrollments",
    response_model=OasisResponse[list[EnrollmentAdminRead]],
    summary="Listar inscripciones (Admin)",
    description="Lista todas las inscripciones de la organización.",
)
async def list_enrollments_admin(
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    journey_id: UUID | None = Query(  # noqa: B008
        None, description="Filtrar por journey"
    ),  # noqa: B008
    status: str | None = Query(  # noqa: B008
        None, description="Filtrar por estado (active, completed, dropped)"
    ),
    skip: int = Query(0, ge=0),  # noqa: B008
    limit: int = Query(50, ge=1, le=100),  # noqa: B008
):
    """
    Lista inscripciones con información del usuario y journey.

    Permite filtrar por journey específico o por estado.
    """
    org_id = ctx["org_id"]

    enrollments, total = await crud.list_enrollments_admin(
        db=db,
        org_id=UUID(org_id),
        journey_id=journey_id,
        status=status,
        skip=skip,
        limit=limit,
    )

    return OasisResponse(
        success=True,
        message=f"Se encontraron {total} inscripciones.",
        data=enrollments,
        meta={"total": total, "skip": skip, "limit": limit},
    )


# =============================================================================
# USER PROGRESS
# =============================================================================


@router.get(
    "/users/{user_id}/progress",
    response_model=OasisResponse[UserProgressSummary],
    summary="Ver progreso de usuario",
    description="Obtiene el progreso detallado de un usuario específico.",
)
async def get_user_progress(
    user_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene estadísticas completas de un usuario:
    - Puntos totales y nivel actual
    - Journeys activos, completados y abandonados
    - Última actividad
    """
    org_id = ctx["org_id"]

    progress = await crud.get_user_progress_admin(db, UUID(org_id), user_id)

    if not progress:
        raise NotFoundError("User", str(user_id))

    return OasisResponse(
        success=True,
        message="Progreso del usuario obtenido.",
        data=progress,
    )


# =============================================================================
# ORGANIZATION ANALYTICS
# =============================================================================


@router.get(
    "/summary",
    response_model=OasisResponse[OrgAnalyticsSummary],
    summary="Resumen de organización",
    description="Obtiene estadísticas generales de la organización.",
)
async def get_org_analytics(
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene un resumen de analytics de toda la organización:
    - Total de usuarios y usuarios activos
    - Total de journeys activos
    - Tasa de completado general
    - Puntos totales otorgados
    """
    org_id = ctx["org_id"]

    analytics = await crud.get_org_analytics(db, UUID(org_id))

    return OasisResponse(
        success=True,
        message="Analytics de organización obtenidos.",
        data=analytics,
    )
