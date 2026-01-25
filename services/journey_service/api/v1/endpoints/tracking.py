"""
Activity tracking endpoint.

Records user activities and awards points.
Organization context required for step-based activities.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from common.auth.security import OrgMemberRequired
from common.database.client import get_admin_client
from common.exceptions import ForbiddenError, InternalError, NotFoundError
from common.middleware import limiter
from common.schemas.responses import OasisResponse
from services.journey_service.crud import journeys as journeys_crud
from services.journey_service.logic.gamification import (
    calculate_points,
    check_and_apply_level_up,
)
from services.journey_service.schemas.tracking import ActivityResponse, ActivityTrack
from supabase import AsyncClient

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_step_belongs_to_org(
    db: AsyncClient,
    step_id: UUID,
    org_id: str,
) -> bool:
    """Verifica que un step pertenezca a un journey de la organización."""
    response = (
        await db.table("journeys.steps")
        .select("journey_id")
        .eq("id", str(step_id))
        .single()
        .execute()
    )

    if not response.data:
        return False

    journey_id = response.data["journey_id"]
    return await journeys_crud.verify_journey_belongs_to_org(db, journey_id, org_id)


@router.post(
    "/event",
    response_model=OasisResponse[ActivityResponse],
    summary="Registrar actividad de usuario",
    description="Procesa eventos (likes, posts, videos) y otorga puntos según reglas.",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Step no pertenece a tu organización"},
        429: {"description": "Rate limit excedido"},
    },
)
@limiter.limit("60/minute")
async def track_activity(
    request: Request,
    payload: ActivityTrack,
    background_tasks: BackgroundTasks,
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Registra una actividad del usuario autenticado y calcula puntos.

    El user_id se obtiene automáticamente del token JWT.
    Requiere header X-Organization-ID para verificar pertenencia.
    """
    user_id = UUID(ctx["id"])
    org_id = ctx["org_id"]
    points_earned = 0
    level_up = False

    try:
        # 1. Si está vinculado a un STEP específico (Journey Lineal)
        if payload.step_id:
            # Verificar que el step pertenece a la organización
            step_belongs = await verify_step_belongs_to_org(db, payload.step_id, org_id)
            if not step_belongs:
                raise ForbiddenError("El step no pertenece a tu organización.")

            step_res = (
                await db.table("journeys.steps")
                .select("gamification_rules")
                .eq("id", str(payload.step_id))
                .single()
                .execute()
            )

            if not step_res.data:
                raise NotFoundError("Step", str(payload.step_id))

            points_earned = await calculate_points(
                step_res.data["gamification_rules"], payload.metadata
            )

            # Marcar paso como completo
            await db.table("journeys.step_completions").insert(
                {
                    "enrollment_id": str(payload.journey_id),
                    "step_id": str(payload.step_id),
                    "user_id": str(user_id),
                    "journey_id": str(payload.journey_id),
                    "points_earned": points_earned,
                    "metadata": payload.metadata,
                }
            ).execute()

        # 2. Si es una actividad general (Community/Resources - "Side Quest")
        else:
            # Reglas base por tipo de actividad
            activity_points = {
                "social_post": 5,
                "video_view": 3,
                "resource_view": 2,
                "comment": 2,
                "like": 1,
            }
            points_earned = activity_points.get(payload.activity_type, 1)

            # Registrar en log de actividades
            await db.table("journeys.user_activities").insert(
                {
                    "user_id": str(user_id),
                    "type": payload.activity_type,
                    "points_awarded": points_earned,
                    "metadata": payload.metadata,
                }
            ).execute()

        # 3. Actualizar Ledger de Puntos (Transaccional)
        new_total = 0
        if points_earned > 0:
            await db.table("journeys.points_ledger").insert(
                {
                    "user_id": str(user_id),
                    "amount": points_earned,
                    "reason": payload.activity_type,
                    "reference_id": str(payload.step_id) if payload.step_id else None,
                }
            ).execute()

            # 4. Calcular total actual
            total_res = await db.rpc(
                "get_user_total_points", {"uid": str(user_id)}
            ).execute()
            new_total = total_res.data or 0

            # 5. Verificar Nivel (En Background para no ralentizar)
            background_tasks.add_task(check_and_apply_level_up, user_id, new_total, db)

        return OasisResponse(
            success=True,
            message="Actividad registrada correctamente.",
            data=ActivityResponse(
                points_earned=points_earned,
                new_total=new_total if points_earned > 0 else None,
                level_up=level_up,
            ),
        )

    except (ForbiddenError, NotFoundError):
        raise
    except Exception as e:
        logger.error(f"Error tracking activity for user {user_id}: {e}")
        raise InternalError(f"Error al registrar actividad: {str(e)}") from e
