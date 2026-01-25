"""
User endpoints for viewing Journeys.

All endpoints require organization membership validation.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from common.auth.security import OrgMemberRequired
from common.database.client import get_admin_client
from common.exceptions import ForbiddenError, NotFoundError
from common.schemas.responses import OasisResponse
from services.journey_service.crud import journeys as crud
from services.journey_service.schemas.journeys import JourneyRead, StepRead
from supabase import AsyncClient

router = APIRouter()


@router.get(
    "/",
    response_model=OasisResponse[list[JourneyRead]],
    summary="Listar journeys disponibles",
    description="Lista los journeys disponibles para el usuario según su organización.",
)
async def list_journeys(
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    is_active: bool | None = Query(True, description="Filtrar por activos"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Lista journeys disponibles para el usuario.

    Requiere header X-Organization-ID para filtrar por organización.
    """
    org_id = ctx.get("org_id")

    if not org_id:
        return OasisResponse(
            success=True,
            message="No hay journeys disponibles.",
            data=[],
            meta={"total": 0, "skip": skip, "limit": limit},
        )

    journeys, total = await crud.get_journeys_for_user(
        db=db,
        org_ids=[org_id],
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


@router.get(
    "/{journey_id}",
    response_model=OasisResponse[JourneyRead],
    summary="Obtener detalle de journey",
    description="Obtiene un journey con todos sus steps.",
)
async def get_journey(
    journey_id: UUID,
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene el detalle de un journey incluyendo sus steps ordenados.

    Requiere header X-Organization-ID y verifica que el journey pertenezca
    a esa organización.
    """
    org_id = ctx["org_id"]

    # Verificar que el journey pertenece a la organización
    belongs = await crud.verify_journey_belongs_to_org(db, journey_id, org_id)
    if not belongs:
        raise ForbiddenError("El journey no pertenece a tu organización.")

    journey = await crud.get_journey_with_steps(db, journey_id)

    if not journey:
        raise NotFoundError("Journey", str(journey_id))

    return OasisResponse(
        success=True,
        message="Journey encontrado.",
        data=journey,
    )


@router.get(
    "/{journey_id}/steps",
    response_model=OasisResponse[list[StepRead]],
    summary="Obtener steps de un journey",
    description="Lista los steps de un journey ordenados.",
)
async def get_journey_steps(
    journey_id: UUID,
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene los steps de un journey ordenados por order_index.

    Requiere header X-Organization-ID y verifica que el journey pertenezca
    a esa organización.
    """
    org_id = ctx["org_id"]

    # Verificar que el journey pertenece a la organización
    belongs = await crud.verify_journey_belongs_to_org(db, journey_id, org_id)
    if not belongs:
        raise ForbiddenError("El journey no pertenece a tu organización.")

    # Verificar que el journey existe
    journey = await crud.get_journey_by_id(db, journey_id)
    if not journey:
        raise NotFoundError("Journey", str(journey_id))

    steps = await crud.get_steps_by_journey(db, journey_id)

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(steps)} steps.",
        data=steps,
    )
