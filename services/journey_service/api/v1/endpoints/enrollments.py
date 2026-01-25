from uuid import UUID

from fastapi import APIRouter, Depends, status

from common.auth.security import OrgMemberRequired, get_current_user
from common.database.client import get_admin_client
from common.errors import ErrorCodes
from common.exceptions import (
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
)
from common.schemas.responses import OasisErrorResponse, OasisResponse
from services.journey_service.crud import enrollments as crud
from services.journey_service.crud import journeys as journeys_crud
from services.journey_service.schemas.enrollments import (
    EnrollmentCreate,
    EnrollmentDetailResponse,
    EnrollmentResponse,
    StepCompletionOut,
)
from supabase import AsyncClient

router = APIRouter()


@router.post(
    "/",
    response_model=OasisResponse[EnrollmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Inscribir usuario autenticado",
    description=(
        "Inscribe al usuario actual en un Journey específico,"
        "inicializando su progreso."
    ),
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Journey no pertenece a tu organización"},
        409: {
            "model": OasisErrorResponse,
            "description": "El usuario ya está inscrito.",
        },
    },
)
async def enroll_user(
    payload: EnrollmentCreate,
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Inscribe al usuario autenticado en un journey.

    El user_id se obtiene automáticamente del token JWT, no del payload.
    Requiere header X-Organization-ID y verifica que el journey pertenezca
    a esa organización.
    """
    user_id = UUID(ctx["id"])
    org_id = ctx["org_id"]

    # 1. Verificar que el journey pertenece a la organización
    belongs = await journeys_crud.verify_journey_belongs_to_org(
        db, payload.journey_id, org_id
    )
    if not belongs:
        raise ForbiddenError("El journey no pertenece a tu organización.")

    # 2. Verificar duplicados
    existing = await crud.get_active_enrollment(db, user_id, payload.journey_id)
    if existing:
        raise ConflictError(
            code=ErrorCodes.ENROLLMENT_ALREADY_EXISTS,
            message="Ya tienes una inscripción activa en este Journey.",
        )

    # 3. Crear inscripción
    try:
        new_enrollment = await crud.create_enrollment(db, user_id, payload)

        response_data = EnrollmentResponse(
            id=new_enrollment["id"],
            user_id=new_enrollment["user_id"],
            journey_id=new_enrollment["journey_id"],
            status=new_enrollment["status"],
            current_step_index=new_enrollment["current_step_index"],
            progress_percentage=0.0,
            started_at=new_enrollment["started_at"],
        )

        return OasisResponse(
            success=True,
            message="Inscripción creada exitosamente.",
            data=response_data,
        )

    except ConflictError:
        raise
    except Exception as e:
        raise InternalError(f"Error al crear inscripción: {str(e)}") from e


@router.get(
    "/me",
    response_model=OasisResponse[list[EnrollmentResponse]],
    summary="Obtener mis inscripciones",
    description="Lista todas las inscripciones del usuario autenticado.",
)
async def get_my_enrollments(
    status_filter: str | None = None,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene todas las inscripciones del usuario autenticado.

    Query params:
        status_filter: Filtrar por estado (active, completed, dropped)
    """
    user_id = UUID(current_user["id"])

    enrollments = await crud.get_user_enrollments(db, user_id, status_filter)

    response_data = [
        EnrollmentResponse(
            id=e["id"],
            user_id=e["user_id"],
            journey_id=e["journey_id"],
            status=e["status"],
            current_step_index=e["current_step_index"],
            progress_percentage=e.get("progress_percentage", 0.0),
            started_at=e["started_at"],
            completed_at=e.get("completed_at"),
        )
        for e in enrollments
    ]

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(response_data)} inscripciones.",
        data=response_data,
    )


@router.get(
    "/{enrollment_id}",
    response_model=OasisResponse[EnrollmentDetailResponse],
    summary="Obtener detalle de inscripción",
    description="Obtiene el detalle de una inscripción con su progreso.",
)
async def get_enrollment_detail(
    enrollment_id: UUID,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene el detalle de una inscripción incluyendo:
    - Información del journey
    - Steps completados
    - Progreso actual
    """
    user_id = UUID(current_user["id"])

    enrollment = await crud.get_enrollment_with_progress(db, enrollment_id)

    if not enrollment:
        raise NotFoundError("Enrollment", str(enrollment_id))

    # Verificar que pertenece al usuario
    if enrollment["user_id"] != str(user_id):
        raise ForbiddenError("No tienes acceso a esta inscripción.")

    return OasisResponse(
        success=True,
        message="Inscripción encontrada.",
        data=enrollment,
    )


@router.get(
    "/{enrollment_id}/progress",
    response_model=OasisResponse[list[StepCompletionOut]],
    summary="Obtener progreso detallado",
    description="Lista los steps completados de una inscripción.",
)
async def get_enrollment_progress(
    enrollment_id: UUID,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene el progreso detallado de una inscripción:
    - Lista de steps con estado (locked, available, completed)
    - Puntos ganados por step
    """
    user_id = UUID(current_user["id"])

    # Verificar ownership
    enrollment = await crud.get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        raise NotFoundError("Enrollment", str(enrollment_id))

    if enrollment["user_id"] != str(user_id):
        raise ForbiddenError("No tienes acceso a esta inscripción.")

    progress = await crud.get_enrollment_step_progress(db, enrollment_id)

    return OasisResponse(
        success=True,
        message=(
            f"Progreso: {len([p for p in progress if p.get('completed')])} "
            "steps completados."
        ),
        data=progress,
    )


@router.post(
    "/{enrollment_id}/complete",
    response_model=OasisResponse[EnrollmentResponse],
    summary="Marcar journey como completado",
    description=(
        "Marca el journey como completado si todos los steps están completos."
    ),
)
async def complete_enrollment(
    enrollment_id: UUID,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Marca un journey como completado.

    Valida que todos los steps obligatorios estén completados.
    """
    user_id = UUID(current_user["id"])

    enrollment = await crud.get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        raise NotFoundError("Enrollment", str(enrollment_id))

    if enrollment["user_id"] != str(user_id):
        raise ForbiddenError("No tienes acceso a esta inscripción.")

    if enrollment["status"] == "completed":
        raise ConflictError(
            code="already_completed",
            message="Este journey ya está completado.",
        )

    # Verificar que se puede completar
    can_complete, message = await crud.can_complete_enrollment(db, enrollment_id)
    if not can_complete:
        raise ConflictError(code="incomplete_steps", message=message)

    # Marcar como completado
    updated = await crud.update_enrollment_status(db, enrollment_id, "completed")

    return OasisResponse(
        success=True,
        message="Journey completado exitosamente.",
        data=EnrollmentResponse(**updated),
    )


@router.post(
    "/{enrollment_id}/drop",
    response_model=OasisResponse[EnrollmentResponse],
    summary="Abandonar journey",
    description="Marca el journey como abandonado.",
)
async def drop_enrollment(
    enrollment_id: UUID,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Abandona un journey activo.

    El progreso se mantiene por si el usuario quiere retomarlo.
    """
    user_id = UUID(current_user["id"])

    enrollment = await crud.get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        raise NotFoundError("Enrollment", str(enrollment_id))

    if enrollment["user_id"] != str(user_id):
        raise ForbiddenError("No tienes acceso a esta inscripción.")

    if enrollment["status"] != "active":
        raise ConflictError(
            code="invalid_status",
            message=(
                f"No se puede abandonar un journey con estado '{enrollment['status']}'."
            ),
        )

    updated = await crud.update_enrollment_status(db, enrollment_id, "dropped")

    return OasisResponse(
        success=True,
        message="Journey abandonado. Puedes retomarlo cuando quieras.",
        data=EnrollmentResponse(**updated),
    )


@router.post(
    "/{enrollment_id}/resume",
    response_model=OasisResponse[EnrollmentResponse],
    summary="Retomar journey abandonado",
    description="Reactiva un journey que fue abandonado.",
)
async def resume_enrollment(
    enrollment_id: UUID,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Retoma un journey abandonado.

    Mantiene el progreso previo.
    """
    user_id = UUID(current_user["id"])

    enrollment = await crud.get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        raise NotFoundError("Enrollment", str(enrollment_id))

    if enrollment["user_id"] != str(user_id):
        raise ForbiddenError("No tienes acceso a esta inscripción.")

    if enrollment["status"] != "dropped":
        raise ConflictError(
            code="invalid_status",
            message=(
                "Solo se pueden retomar journeys abandonados."
                "Estado actual: '{enrollment['status']}'."
            ),
        )

    updated = await crud.update_enrollment_status(db, enrollment_id, "active")

    return OasisResponse(
        success=True,
        message="Journey reactivado. Continúa donde lo dejaste.",
        data=EnrollmentResponse(**updated),
    )
