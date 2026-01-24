from uuid import UUID

from services.journey_service.schemas.enrollments import EnrollmentCreate
from supabase import AsyncClient


async def get_active_enrollment(
    db: AsyncClient, user_id: UUID, journey_id: UUID
) -> dict | None:
    """Verifica si ya existe una inscripción activa."""
    response = (
        await db.table("journeys.enrollments")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("journey_id", str(journey_id))
        .in_("status", ["active", "completed"])
        .execute()
    )

    return response.data[0] if response.data else None


async def create_enrollment(
    db: AsyncClient, user_id: UUID, enrollment: EnrollmentCreate
) -> dict:
    """
    Crea una nueva inscripción en la base de datos.

    Args:
        db: Cliente de Supabase
        user_id: UUID del usuario autenticado (del token JWT)
        enrollment: Datos de la inscripción
    """
    payload = {
        "user_id": str(user_id),
        "journey_id": str(enrollment.journey_id),
        "status": "active",
        "current_step_index": 0,
        "metadata": enrollment.metadata or {},
    }

    response = await db.table("journeys.enrollments").insert(payload).execute()
    return response.data[0]


async def get_enrollment_by_id(db: AsyncClient, enrollment_id: UUID) -> dict | None:
    """Obtiene una inscripción por su ID."""
    response = (
        await db.table("journeys.enrollments")
        .select("*")
        .eq("id", str(enrollment_id))
        .single()
        .execute()
    )
    return response.data


async def get_user_enrollments(
    db: AsyncClient, user_id: UUID, status: str | None = None
) -> list[dict]:
    """Obtiene todas las inscripciones de un usuario."""
    query = db.table("journeys.enrollments").select("*").eq("user_id", str(user_id))

    if status:
        query = query.eq("status", status)

    response = await query.order("started_at", desc=True).execute()
    return response.data or []
