import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from common.auth.security import get_current_user
from common.database.client import get_admin_client
from common.exceptions import InternalError
from common.middleware import limiter
from common.schemas.responses import OasisResponse
from services.journey_service.logic.gamification import (
    calculate_points,
    check_and_apply_level_up,
)
from services.journey_service.schemas.tracking import ActivityResponse, ActivityTrack
from supabase import AsyncClient

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/event",
    response_model=OasisResponse[ActivityResponse],
    summary="Registrar actividad de usuario",
    description="Procesa eventos (likes, posts, videos) y otorga puntos según reglas.",
    responses={
        401: {"description": "No autenticado"},
        429: {"description": "Rate limit excedido"},
    },
)
@limiter.limit("60/minute")  # Más restrictivo para evitar abuse de puntos
async def track_activity(
    request: Request,  # Requerido por slowapi
    payload: ActivityTrack,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Registra una actividad del usuario autenticado y calcula puntos.

    El user_id se obtiene automáticamente del token JWT.
    """
    user_id = UUID(current_user["id"])
    points_earned = 0
    level_up = False

    try:
        # 1. Si está vinculado a un STEP específico (Journey Lineal)
        if payload.step_id:
            step_res = (
                await db.table("journeys.steps")
                .select("gamification_rules")
                .eq("id", str(payload.step_id))
                .single()
                .execute()
            )

            if step_res.data:
                points_earned = await calculate_points(
                    step_res.data["gamification_rules"], payload.metadata
                )

                # Marcar paso como completo
                await db.table("journeys.step_completions").insert(
                    {
                        "enrollment_id": str(
                            payload.journey_id
                        ),  # Necesita enrollment_id real
                        "step_id": str(payload.step_id),
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

    except Exception as e:
        logger.error(f"Error tracking activity for user {user_id}: {e}")
        raise InternalError(f"Error al registrar actividad: {str(e)}") from e
