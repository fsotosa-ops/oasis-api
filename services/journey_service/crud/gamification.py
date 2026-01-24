from uuid import UUID

from supabase import AsyncClient


async def get_user_total_points(db: AsyncClient, user_id: UUID) -> int:
    """Obtiene el total de puntos de un usuario."""
    response = await db.rpc("get_user_total_points", {"uid": str(user_id)}).execute()
    return response.data or 0


async def get_user_current_level(
    db: AsyncClient, user_id: UUID, org_id: UUID | None = None
) -> dict | None:
    """Obtiene el nivel actual del usuario."""
    params = {"uid": str(user_id)}
    if org_id:
        params["org_id"] = str(org_id)

    response = await db.rpc("get_user_current_level", params).execute()

    if response.data and len(response.data) > 0:
        return response.data[0]
    return None


async def get_user_stats(db: AsyncClient, user_id: UUID) -> dict:
    """Obtiene estadísticas completas del usuario."""
    # Total de puntos
    total_points = await get_user_total_points(db, user_id)

    # Nivel actual
    level_info = await get_user_current_level(db, user_id)

    # Enrollments activos y completados
    enrollments_response = (
        await db.table("journeys.enrollments")
        .select("status", count="exact")
        .eq("user_id", str(user_id))
        .execute()
    )

    active_enrollments = 0
    completed_journeys = 0
    for e in enrollments_response.data or []:
        if e["status"] == "active":
            active_enrollments += 1
        elif e["status"] == "completed":
            completed_journeys += 1

    # Total de actividades
    activities_response = (
        await db.table("journeys.user_activities")
        .select("id", count="exact")
        .eq("user_id", str(user_id))
        .execute()
    )
    total_activities = activities_response.count or 0

    # Siguiente nivel
    next_level = None
    points_to_next = None
    if level_info and level_info.get("next_level_points"):
        next_level_response = (
            await db.table("journeys.levels")
            .select("*")
            .eq("min_points", level_info["next_level_points"])
            .single()
            .execute()
        )
        if next_level_response.data:
            next_level = next_level_response.data
            points_to_next = level_info["next_level_points"] - total_points

    return {
        "user_id": str(user_id),
        "total_points": total_points,
        "current_level": (
            {
                "id": level_info["level_id"],
                "name": level_info["level_name"],
                "min_points": level_info["min_points"],
            }
            if level_info
            else None
        ),
        "next_level": (
            {
                "id": next_level["id"],
                "name": next_level["name"],
                "min_points": next_level["min_points"],
                "icon_url": next_level.get("icon_url"),
            }
            if next_level
            else None
        ),
        "points_to_next_level": points_to_next,
        "active_enrollments": active_enrollments,
        "completed_journeys": completed_journeys,
        "total_activities": total_activities,
    }


async def get_user_rewards(
    db: AsyncClient, user_id: UUID, limit: int = 50
) -> list[dict]:
    """Obtiene las recompensas/insignias del usuario."""
    response = (
        await db.table("journeys.user_rewards")
        .select("*, rewards_catalog(*)")
        .eq("user_id", str(user_id))
        .order("earned_at", desc=True)
        .limit(limit)
        .execute()
    )

    rewards = []
    for r in response.data or []:
        catalog = r.get("rewards_catalog", {})
        rewards.append(
            {
                "id": r["id"],
                "reward_id": r["reward_id"],
                "name": catalog.get("name", "Unknown"),
                "description": catalog.get("description"),
                "type": catalog.get("type", "badge"),
                "icon_url": catalog.get("icon_url"),
                "earned_at": r["earned_at"],
                "journey_id": r.get("journey_id"),
            }
        )

    return rewards


async def get_user_activity_log(
    db: AsyncClient, user_id: UUID, limit: int = 50
) -> list[dict]:
    """Obtiene el historial de actividades del usuario."""
    response = (
        await db.table("journeys.user_activities")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_user_points_history(
    db: AsyncClient, user_id: UUID, limit: int = 50
) -> list[dict]:
    """Obtiene el historial de puntos del usuario."""
    response = (
        await db.table("journeys.points_ledger")
        .select("*")
        .eq("user_id", str(user_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_leaderboard(
    db: AsyncClient,
    org_id: UUID | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Obtiene el ranking de usuarios por puntos.

    Args:
        db: Cliente Supabase
        org_id: Filtrar por organización (None = global)
        limit: Número de posiciones
    """
    # Query para obtener puntos agrupados por usuario
    # Esto requiere una función RPC o view en la DB para ser eficiente
    # Por ahora hacemos una aproximación

    response = (
        await db.table("journeys.points_ledger").select("user_id, amount").execute()
    )

    # Agregar puntos por usuario
    user_points: dict[str, int] = {}
    for entry in response.data or []:
        uid = entry["user_id"]
        user_points[uid] = user_points.get(uid, 0) + entry["amount"]

    # Ordenar y tomar top N
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)[:limit]

    # Obtener datos de perfil
    leaderboard = []
    for rank, (user_id, points) in enumerate(sorted_users, 1):
        profile_response = (
            await db.table("profiles")
            .select("full_name, avatar_url")
            .eq("id", user_id)
            .single()
            .execute()
        )
        profile = profile_response.data or {}

        leaderboard.append(
            {
                "rank": rank,
                "user_id": user_id,
                "full_name": profile.get("full_name", "Usuario"),
                "avatar_url": profile.get("avatar_url"),
                "total_points": points,
                "level_name": None,  # Se podría calcular
            }
        )

    return leaderboard


async def get_available_levels(
    db: AsyncClient, org_id: UUID | None = None
) -> list[dict]:
    """Obtiene los niveles disponibles."""
    query = db.table("journeys.levels").select("*")

    if org_id:
        # Niveles de la org o globales (org_id IS NULL)
        query = query.or_(f"organization_id.eq.{org_id},organization_id.is.null")
    else:
        query = query.is_("organization_id", "null")

    response = await query.order("min_points").execute()
    return response.data or []
