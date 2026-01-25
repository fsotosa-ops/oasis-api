"""
Admin endpoints for Journey and Step management.

Authorization: Requires 'owner' or 'admin' role in the organization.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common.auth.security import OrgRoleChecker
from common.database.client import get_admin_client
from common.exceptions import ForbiddenError, NotFoundError
from common.schemas.responses import OasisResponse
from services.journey_service.crud import admin as crud
from services.journey_service.schemas.admin import (
    JourneyAdminRead,
    JourneyCreate,
    JourneyStats,
    JourneyUpdate,
    StepAdminRead,
    StepCreate,
    StepReorderRequest,
    StepUpdate,
)
from supabase import AsyncClient

router = APIRouter()

# Role checker for admin operations
AdminRequired = OrgRoleChecker(["owner", "admin"])


# =============================================================================
# JOURNEY ENDPOINTS
# =============================================================================


@router.get(
    "/",
    response_model=OasisResponse[list[JourneyAdminRead]],
    summary="Listar journeys (Admin)",
    description="Lista todos los journeys de la organización con estadísticas.",
)
async def list_journeys_admin(
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    is_active: bool | None = Query(None, description="Filtrar por estado activo"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Lista journeys con estadísticas de enrollments."""
    org_id = ctx["org_id"]

    journeys, total = await crud.list_journeys_admin(
        db=db,
        org_id=UUID(org_id),
        is_active=is_active,
        skip=skip,
        limit=limit,
    )

    return OasisResponse(
        success=True,
        message=f"Se encontraron {total} journeys.",
        data=journeys,
        meta={"total": total, "skip": skip, "limit": limit},
    )


@router.post(
    "/",
    response_model=OasisResponse[JourneyAdminRead],
    status_code=status.HTTP_201_CREATED,
    summary="Crear journey",
    description="Crea un nuevo journey para la organización.",
)
async def create_journey(
    payload: JourneyCreate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Crea un nuevo journey.

    El journey se crea como borrador (is_active=False) por defecto.
    Use POST /journeys/{id}/publish para activarlo.
    """
    org_id = ctx["org_id"]

    journey = await crud.create_journey(db, UUID(org_id), payload)

    # Add default stats
    journey["total_steps"] = 0
    journey["total_enrollments"] = 0
    journey["active_enrollments"] = 0
    journey["completed_enrollments"] = 0
    journey["completion_rate"] = 0.0

    return OasisResponse(
        success=True,
        message="Journey creado exitosamente.",
        data=journey,
    )


@router.get(
    "/{journey_id}",
    response_model=OasisResponse[JourneyAdminRead],
    summary="Obtener journey (Admin)",
    description="Obtiene un journey con estadísticas detalladas.",
)
async def get_journey_admin(
    journey_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Obtiene un journey con sus estadísticas."""
    org_id = ctx["org_id"]

    # Verify ownership
    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    journey = await crud.get_journey_admin(db, journey_id)

    if not journey:
        raise NotFoundError("Journey", str(journey_id))

    return OasisResponse(
        success=True,
        message="Journey encontrado.",
        data=journey,
    )


@router.put(
    "/{journey_id}",
    response_model=OasisResponse[JourneyAdminRead],
    summary="Actualizar journey",
    description="Actualiza los datos de un journey.",
)
async def update_journey(
    journey_id: UUID,
    payload: JourneyUpdate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Actualiza un journey existente."""
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    updated = await crud.update_journey(db, journey_id, payload)

    if not updated:
        raise NotFoundError("Journey", str(journey_id))

    # Get full stats
    journey = await crud.get_journey_admin(db, journey_id)

    return OasisResponse(
        success=True,
        message="Journey actualizado exitosamente.",
        data=journey,
    )


@router.delete(
    "/{journey_id}",
    response_model=OasisResponse[dict],
    summary="Eliminar journey",
    description="Elimina un journey y todos sus datos asociados.",
)
async def delete_journey(
    journey_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Elimina un journey.

    ADVERTENCIA: Esto elimina también todos los steps, enrollments y progreso.
    """
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    deleted = await crud.delete_journey(db, journey_id)

    if not deleted:
        raise NotFoundError("Journey", str(journey_id))

    return OasisResponse(
        success=True,
        message="Journey eliminado exitosamente.",
        data={"deleted_id": str(journey_id)},
    )


@router.post(
    "/{journey_id}/publish",
    response_model=OasisResponse[JourneyAdminRead],
    summary="Publicar journey",
    description="Activa un journey para que sea visible a los usuarios.",
)
async def publish_journey(
    journey_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Publica (activa) un journey."""
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    await crud.publish_journey(db, journey_id)
    journey = await crud.get_journey_admin(db, journey_id)

    return OasisResponse(
        success=True,
        message="Journey publicado exitosamente.",
        data=journey,
    )


@router.post(
    "/{journey_id}/archive",
    response_model=OasisResponse[JourneyAdminRead],
    summary="Archivar journey",
    description="Desactiva un journey. Los enrollments existentes se mantienen.",
)
async def archive_journey(
    journey_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Archiva (desactiva) un journey."""
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    await crud.archive_journey(db, journey_id)
    journey = await crud.get_journey_admin(db, journey_id)

    return OasisResponse(
        success=True,
        message="Journey archivado exitosamente.",
        data=journey,
    )


@router.get(
    "/{journey_id}/stats",
    response_model=OasisResponse[JourneyStats],
    summary="Estadísticas de journey",
    description="Obtiene estadísticas detalladas de un journey.",
)
async def get_journey_stats(
    journey_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Obtiene estadísticas completas de un journey."""
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    stats = await crud.get_journey_stats(db, journey_id)

    if not stats:
        raise NotFoundError("Journey", str(journey_id))

    return OasisResponse(
        success=True,
        message="Estadísticas obtenidas.",
        data=stats,
    )


# =============================================================================
# STEP ENDPOINTS
# =============================================================================


@router.get(
    "/{journey_id}/steps",
    response_model=OasisResponse[list[StepAdminRead]],
    summary="Listar steps (Admin)",
    description="Lista todos los steps de un journey con estadísticas.",
)
async def list_steps_admin(
    journey_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Lista steps con estadísticas de completado."""
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    steps = await crud.list_steps_admin(db, journey_id)

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(steps)} steps.",
        data=steps,
    )


@router.post(
    "/{journey_id}/steps",
    response_model=OasisResponse[StepAdminRead],
    status_code=status.HTTP_201_CREATED,
    summary="Crear step",
    description="Crea un nuevo step en el journey.",
)
async def create_step(
    journey_id: UUID,
    payload: StepCreate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Crea un nuevo step.

    Si no se especifica order_index, se agrega al final.
    """
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    step = await crud.create_step(db, journey_id, payload)

    # Add default stats
    step["total_completions"] = 0
    step["average_points"] = 0.0

    return OasisResponse(
        success=True,
        message="Step creado exitosamente.",
        data=step,
    )


@router.put(
    "/{journey_id}/steps/{step_id}",
    response_model=OasisResponse[StepAdminRead],
    summary="Actualizar step",
    description="Actualiza los datos de un step.",
)
async def update_step(
    journey_id: UUID,
    step_id: UUID,
    payload: StepUpdate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Actualiza un step existente."""
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    updated = await crud.update_step(db, step_id, payload)

    if not updated:
        raise NotFoundError("Step", str(step_id))

    step = await crud.get_step_admin(db, step_id)

    return OasisResponse(
        success=True,
        message="Step actualizado exitosamente.",
        data=step,
    )


@router.delete(
    "/{journey_id}/steps/{step_id}",
    response_model=OasisResponse[dict],
    summary="Eliminar step",
    description="Elimina un step del journey.",
)
async def delete_step(
    journey_id: UUID,
    step_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Elimina un step.

    ADVERTENCIA: Esto elimina también los registros de completado.
    """
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    deleted = await crud.delete_step(db, step_id)

    if not deleted:
        raise NotFoundError("Step", str(step_id))

    return OasisResponse(
        success=True,
        message="Step eliminado exitosamente.",
        data={"deleted_id": str(step_id)},
    )


@router.post(
    "/{journey_id}/steps/reorder",
    response_model=OasisResponse[list[StepAdminRead]],
    summary="Reordenar steps",
    description="Cambia el orden de los steps en un journey.",
)
async def reorder_steps(
    journey_id: UUID,
    payload: StepReorderRequest,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Reordena los steps de un journey.

    Envía una lista de {step_id, new_index} para definir el nuevo orden.
    """
    org_id = ctx["org_id"]

    if not await crud.verify_journey_ownership(db, journey_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este journey.")

    step_orders = [
        {"step_id": item.step_id, "new_index": item.new_index} for item in payload.steps
    ]

    steps = await crud.reorder_steps(db, journey_id, step_orders)

    return OasisResponse(
        success=True,
        message="Steps reordenados exitosamente.",
        data=steps,
    )
