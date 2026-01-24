from datetime import UTC, datetime
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


async def get_enrollment_with_progress(
    db: AsyncClient, enrollment_id: UUID
) -> dict | None:
    """
    Obtiene una inscripción con información del journey y progreso detallado.
    """
    # Obtener enrollment
    enrollment = await get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        return None

    journey_id = enrollment["journey_id"]

    # Obtener journey
    journey_response = (
        await db.table("journeys.journeys")
        .select("id, title, slug, description, thumbnail_url")
        .eq("id", journey_id)
        .single()
        .execute()
    )
    journey = journey_response.data

    # Obtener steps del journey
    steps_response = (
        await db.table("journeys.steps")
        .select("id, title, type, order_index")
        .eq("journey_id", journey_id)
        .order("order_index")
        .execute()
    )
    all_steps = steps_response.data or []

    # Obtener completions del enrollment
    completions_response = (
        await db.table("journeys.step_completions")
        .select("step_id, completed_at, points_earned")
        .eq("enrollment_id", str(enrollment_id))
        .execute()
    )
    completions = {c["step_id"]: c for c in (completions_response.data or [])}

    # Construir progreso por step
    steps_progress = []
    completed_count = 0
    current_step_index = enrollment.get("current_step_index", 0)

    for idx, step in enumerate(all_steps):
        step_id = step["id"]
        completion = completions.get(step_id)

        if completion:
            status = "completed"
            completed_count += 1
        elif idx <= current_step_index:
            status = "available"
        else:
            status = "locked"

        steps_progress.append(
            {
                "step_id": step_id,
                "title": step["title"],
                "type": step["type"],
                "order_index": step["order_index"],
                "status": status,
                "completed_at": completion["completed_at"] if completion else None,
                "points_earned": completion["points_earned"] if completion else 0,
            }
        )

    # Agregar info del journey
    if journey:
        journey["total_steps"] = len(all_steps)

    return {
        **enrollment,
        "journey": journey,
        "steps_progress": steps_progress,
        "completed_steps": completed_count,
        "total_steps": len(all_steps),
    }


async def get_enrollment_step_progress(
    db: AsyncClient, enrollment_id: UUID
) -> list[dict]:
    """
    Obtiene el progreso detallado de steps para una inscripción.
    """
    enrollment = await get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        return []

    journey_id = enrollment["journey_id"]

    # Obtener steps
    steps_response = (
        await db.table("journeys.steps")
        .select("id, title, type, order_index")
        .eq("journey_id", journey_id)
        .order("order_index")
        .execute()
    )
    all_steps = steps_response.data or []

    # Obtener completions
    completions_response = (
        await db.table("journeys.step_completions")
        .select("*")
        .eq("enrollment_id", str(enrollment_id))
        .execute()
    )
    completions = {c["step_id"]: c for c in (completions_response.data or [])}

    current_index = enrollment.get("current_step_index", 0)
    progress = []

    for idx, step in enumerate(all_steps):
        step_id = step["id"]
        completion = completions.get(step_id)

        if completion:
            status = "completed"
        elif idx <= current_index:
            status = "available"
        else:
            status = "locked"

        progress.append(
            {
                "step_id": step_id,
                "title": step["title"],
                "type": step["type"],
                "order_index": step["order_index"],
                "status": status,
                "completed_at": completion["completed_at"] if completion else None,
                "points_earned": completion["points_earned"] if completion else 0,
                "completed": completion is not None,
            }
        )

    return progress


async def can_complete_enrollment(
    db: AsyncClient, enrollment_id: UUID
) -> tuple[bool, str]:
    """
    Verifica si un enrollment puede ser marcado como completado.

    Returns:
        (can_complete, message)
    """
    enrollment = await get_enrollment_by_id(db, enrollment_id)
    if not enrollment:
        return False, "Inscripción no encontrada."

    journey_id = enrollment["journey_id"]

    # Contar steps totales
    steps_response = (
        await db.table("journeys.steps")
        .select("id", count="exact")
        .eq("journey_id", journey_id)
        .execute()
    )
    total_steps = steps_response.count or 0

    # Contar steps completados
    completions_response = (
        await db.table("journeys.step_completions")
        .select("id", count="exact")
        .eq("enrollment_id", str(enrollment_id))
        .execute()
    )
    completed_steps = completions_response.count or 0

    if completed_steps < total_steps:
        return False, f"Faltan {total_steps - completed_steps} steps por completar."

    return True, "Todos los steps completados."


async def update_enrollment_status(
    db: AsyncClient, enrollment_id: UUID, new_status: str
) -> dict:
    """
    Actualiza el estado de una inscripción.

    Args:
        new_status: 'active', 'completed', 'dropped', 'pending'
    """
    update_data = {"status": new_status}

    if new_status == "completed":
        update_data["completed_at"] = datetime.now(UTC).isoformat()

    response = (
        await db.table("journeys.enrollments")
        .update(update_data)
        .eq("id", str(enrollment_id))
        .execute()
    )

    return response.data[0] if response.data else {}


async def complete_step(
    db: AsyncClient,
    enrollment_id: UUID,
    step_id: UUID,
    points_earned: int = 0,
    metadata: dict | None = None,
) -> dict:
    """
    Marca un step como completado para una inscripción.

    El trigger de la BD actualiza automáticamente progress_percentage.
    """
    payload = {
        "enrollment_id": str(enrollment_id),
        "step_id": str(step_id),
        "points_earned": points_earned,
        "metadata": metadata or {},
    }

    response = await db.table("journeys.step_completions").insert(payload).execute()

    return response.data[0] if response.data else {}
