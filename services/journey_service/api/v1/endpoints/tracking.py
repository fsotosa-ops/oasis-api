"""
Activity tracking endpoint.

Records user activities and awards points.
Organization context required for step-based activities.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.auth.security import OrgMemberRequired
from common.database.client import get_admin_client
from common.exceptions import ForbiddenError, InternalError, NotFoundError
from common.middleware import limiter
from common.schemas.responses import OasisResponse
from services.journey_service.core.config import settings
from services.journey_service.crud import journeys as journeys_crud
from services.journey_service.logic.gamification import (
    calculate_points,
    check_and_apply_level_up,
)
from services.journey_service.schemas.tracking import (
    ActivityResponse,
    ActivityTrack,
    ExternalEventPayload,
    ExternalEventResponse,
)
from supabase import AsyncClient

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer()


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


# ============================================================================
# Service-to-Service Authentication
# ============================================================================


async def verify_service_token(
    auth: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> bool:
    """
    Verify service-to-service authentication token.

    This is used for internal service communication (e.g., webhook_service).
    """
    expected_token = settings.SERVICE_TO_SERVICE_TOKEN

    if not expected_token:
        logger.error("SERVICE_TO_SERVICE_TOKEN not configured")
        raise HTTPException(
            status_code=503,
            detail="Service authentication not configured",
        )

    if auth.credentials != expected_token:
        logger.warning("Invalid service token received")
        raise HTTPException(
            status_code=401,
            detail="Invalid service token",
        )

    return True


# ============================================================================
# External Event Processing (from webhook_service)
# ============================================================================


@router.post(
    "/external-event",
    response_model=OasisResponse[ExternalEventResponse],
    summary="Process external event from webhook service",
    description=(
        "Receives normalized events from webhook_service"
        "and processes step completions."
    ),
    responses={
        401: {"description": "Invalid service token"},
        409: {"description": "Event already processed (idempotent)"},
        503: {"description": "Service authentication not configured"},
    },
)
async def process_external_event(
    payload: ExternalEventPayload,
    background_tasks: BackgroundTasks,
    x_event_source: Annotated[str | None, Header()] = None,
    _auth: bool = Depends(verify_service_token),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Process an external event from the webhook service.

    This endpoint:
    1. Verifies the event hasn't been processed (idempotency)
    2. Resolves the user from user_identifier
    3. Finds associated step via form_id or resource_id
    4. Records step completion and awards points

    Used for:
    - Typeform form submissions (completing training steps)
    - Stripe payments (completing payment steps)
    - Other external integrations
    """
    logger.info(
        f"Processing external event: {payload.source}/{payload.event_type} "
        f"(external_id: {payload.external_id})"
    )

    # 1. Idempotency check - has this event been processed?
    if payload.external_id:
        existing = (
            await db.table("journeys.step_completions")
            .select("id")
            .eq("external_event_id", payload.external_id)
            .limit(1)
            .execute()
        )

        if existing.data:
            logger.info(f"Event {payload.external_id} already processed, skipping")
            return OasisResponse(
                success=True,
                message="Event already processed",
                data=ExternalEventResponse(
                    processed=False,
                    message="Event already processed (idempotent)",
                ),
            )

    # 2. Extract traceability from metadata
    metadata = payload.metadata or {}
    step_id = metadata.get("step_id")
    enrollment_id = metadata.get("enrollment_id")
    journey_id = metadata.get("journey_id")
    form_id = metadata.get("form_id") or payload.resource_id

    # 3. Resolve user from identifier
    user_id = None
    if payload.user_identifier:
        # Try to find user by ID first, then by email
        user_res = (
            await db.table("profiles")
            .select("id")
            .or_(f"id.eq.{payload.user_identifier},email.eq.{payload.user_identifier}")
            .limit(1)
            .execute()
        )

        if user_res.data:
            user_id = user_res.data[0]["id"]

    if not user_id:
        logger.warning(
            f"Could not resolve user for event {payload.external_id}: "
            f"identifier={payload.user_identifier}"
        )
        return OasisResponse(
            success=True,
            message="User not found, event logged but not processed",
            data=ExternalEventResponse(
                processed=False,
                message="User could not be resolved from identifier",
            ),
        )

    # 4. If no step_id, try to find step by form_id/resource_id
    if not step_id and form_id:
        step_res = (
            await db.table("journeys.steps")
            .select("id, gamification_rules, journey_id")
            .contains("external_config", {"form_id": form_id})
            .limit(1)
            .execute()
        )

        if step_res.data:
            step_id = step_res.data[0]["id"]
            journey_id = journey_id or step_res.data[0]["journey_id"]

    # 5. Process step completion if we have enough context
    points_earned = 0
    step_completed = False

    if step_id:
        try:
            # Get step details
            step_res = (
                await db.table("journeys.steps")
                .select("gamification_rules, journey_id")
                .eq("id", step_id)
                .single()
                .execute()
            )

            if step_res.data:
                # Calculate points
                rules = step_res.data.get("gamification_rules", {})
                points_earned = await calculate_points(rules, metadata)
                journey_id = journey_id or step_res.data["journey_id"]

                # Find or create enrollment
                if not enrollment_id and journey_id:
                    enrollment_res = (
                        await db.table("journeys.enrollments")
                        .select("id")
                        .eq("user_id", user_id)
                        .eq("journey_id", journey_id)
                        .limit(1)
                        .execute()
                    )

                    if enrollment_res.data:
                        enrollment_id = enrollment_res.data[0]["id"]

                # Record step completion
                await db.table("journeys.step_completions").insert(
                    {
                        "user_id": user_id,
                        "step_id": step_id,
                        "journey_id": journey_id,
                        "enrollment_id": enrollment_id,
                        "points_earned": points_earned,
                        "external_event_id": payload.external_id,
                        "metadata": {
                            "source": payload.source,
                            "event_type": payload.event_type,
                            "resource_id": payload.resource_id,
                            **metadata,
                        },
                    }
                ).execute()

                step_completed = True
                logger.info(
                    f"Step {step_id} completed for user {user_id}, "
                    f"points: {points_earned}"
                )

                # Award points
                if points_earned > 0:
                    await db.table("journeys.points_ledger").insert(
                        {
                            "user_id": user_id,
                            "amount": points_earned,
                            "reason": f"{payload.source}_{payload.event_type}",
                            "reference_id": step_id,
                        }
                    ).execute()

                    # Check for level up in background
                    total_res = await db.rpc(
                        "get_user_total_points", {"uid": user_id}
                    ).execute()
                    new_total = total_res.data or 0
                    background_tasks.add_task(
                        check_and_apply_level_up, UUID(user_id), new_total, db
                    )

        except Exception as e:
            logger.error(f"Error processing step completion: {e}")
            # Don't fail the whole request, just log
    else:
        # Log as general activity if no step context
        await db.table("journeys.user_activities").insert(
            {
                "user_id": user_id,
                "type": f"external_{payload.source}_{payload.event_type}",
                "points_awarded": 0,
                "metadata": {
                    "external_id": payload.external_id,
                    "resource_id": payload.resource_id,
                    **metadata,
                },
            }
        ).execute()

    return OasisResponse(
        success=True,
        message="External event processed successfully",
        data=ExternalEventResponse(
            processed=True,
            message="Event processed" + (", step completed" if step_completed else ""),
            points_earned=points_earned,
            step_completed=step_completed,
        ),
    )
