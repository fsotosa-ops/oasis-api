from uuid import UUID

from fastapi import APIRouter, Depends, status

from common.auth.security import get_current_user
from common.database.client import get_admin_client
from common.errors import ErrorCodes
from common.exceptions import ConflictError, InternalError
from common.schemas.responses import OasisErrorResponse, OasisResponse
from services.journey_service.crud import enrollments as crud
from services.journey_service.schemas.enrollments import (
    EnrollmentCreate,
    EnrollmentResponse,
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
        409: {
            "model": OasisErrorResponse,
            "description": "El usuario ya está inscrito.",
        },
    },
)
async def enroll_user(
    payload: EnrollmentCreate,
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Inscribe al usuario autenticado en un journey.

    El user_id se obtiene automáticamente del token JWT, no del payload.
    """
    user_id = UUID(current_user["id"])

    # 1. Verificar duplicados
    existing = await crud.get_active_enrollment(db, user_id, payload.journey_id)
    if existing:
        raise ConflictError(
            code=ErrorCodes.ENROLLMENT_ALREADY_EXISTS,
            message="Ya tienes una inscripción activa en este Journey.",
        )

    # 2. Crear inscripción
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
