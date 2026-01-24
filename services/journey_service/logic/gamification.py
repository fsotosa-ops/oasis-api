from uuid import UUID

from supabase import AsyncClient


async def calculate_points(rules: dict, activity_metadata: dict) -> int:
    """
    Evalúa las reglas JSONB contra la metadata de la actividad.
    """
    points = rules.get("points_base", 0)
    bonus_rules = rules.get("bonus_rules", {})

    # Ejemplo: Si es un video, y lo vio completo (progress = 100%)
    if bonus_rules:
        if "min_progress" in bonus_rules:
            user_progress = activity_metadata.get("progress", 0)
            if user_progress >= bonus_rules["min_progress"]:
                points += bonus_rules.get("bonus_points", 0)

        # Ejemplo: Si es un post largo en la comunidad
        if "min_chars" in bonus_rules:
            content_length = activity_metadata.get("char_count", 0)
            if content_length >= bonus_rules["min_chars"]:
                points += bonus_rules.get("bonus_points", 0)

    return points


async def check_and_apply_level_up(
    user_id: UUID, current_total_points: int, db: AsyncClient
) -> dict | None:
    """
    Verifica si el usuario alcanzó un nuevo nivel.
    """
    # Buscar el nivel más alto alcanzable
    response = (
        await db.table("journeys.levels")
        .select("*")
        .lte("min_points", current_total_points)
        .order("min_points", desc=True)
        .limit(1)
        .execute()
    )

    if response.data:
        new_level = response.data[0]
        # Aquí podrías comparar con el nivel anterior guardado en el perfil
        # y retornar el objeto nivel si hubo cambio.
        return new_level

    return None
