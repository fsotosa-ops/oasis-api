from uuid import UUID

from supabase import AsyncClient


async def get_journeys_for_user(
    db: AsyncClient,
    org_ids: list[str],
    is_active: bool | None = True,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    """
    Obtiene journeys disponibles para un usuario basado en sus organizaciones.

    Args:
        db: Cliente Supabase
        org_ids: Lista de IDs de organizaciones del usuario
        is_active: Filtrar por activos (None = todos)
        skip: Offset para paginación
        limit: Límite de resultados
    """
    query = (
        db.table("journeys.journeys")
        .select("*", count="exact")
        .in_("organization_id", org_ids)
    )

    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = (
        await query.order("created_at", desc=True)
        .range(skip, skip + limit - 1)
        .execute()
    )

    return response.data or [], response.count or 0


async def get_journey_by_id(db: AsyncClient, journey_id: UUID) -> dict | None:
    """Obtiene un journey por ID."""
    response = (
        await db.table("journeys.journeys")
        .select("*")
        .eq("id", str(journey_id))
        .single()
        .execute()
    )
    return response.data


async def get_journey_with_steps(db: AsyncClient, journey_id: UUID) -> dict | None:
    """Obtiene un journey con todos sus steps ordenados."""
    # Obtener journey
    journey_response = (
        await db.table("journeys.journeys")
        .select("*")
        .eq("id", str(journey_id))
        .single()
        .execute()
    )

    if not journey_response.data:
        return None

    journey = journey_response.data

    # Obtener steps ordenados
    steps_response = (
        await db.table("journeys.steps")
        .select("*")
        .eq("journey_id", str(journey_id))
        .order("order_index")
        .execute()
    )

    journey["steps"] = steps_response.data or []
    return journey


async def get_steps_by_journey(db: AsyncClient, journey_id: UUID) -> list[dict]:
    """Obtiene los steps de un journey ordenados."""
    response = (
        await db.table("journeys.steps")
        .select("*")
        .eq("journey_id", str(journey_id))
        .order("order_index")
        .execute()
    )
    return response.data or []


async def get_step_by_id(db: AsyncClient, step_id: UUID) -> dict | None:
    """Obtiene un step por ID."""
    response = (
        await db.table("journeys.steps")
        .select("*")
        .eq("id", str(step_id))
        .single()
        .execute()
    )
    return response.data


async def verify_journey_belongs_to_org(
    db: AsyncClient,
    journey_id: UUID,
    org_id: str,
) -> bool:
    """
    Verifica que un journey pertenezca a una organización específica.

    Args:
        db: Cliente Supabase
        journey_id: ID del journey a verificar
        org_id: ID de la organización esperada

    Returns:
        True si el journey pertenece a la organización, False en caso contrario
    """
    response = (
        await db.table("journeys.journeys")
        .select("id")
        .eq("id", str(journey_id))
        .eq("organization_id", org_id)
        .execute()
    )
    return len(response.data) > 0 if response.data else False
