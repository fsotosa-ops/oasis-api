"""
User gamification endpoints.

Stats, rewards, activity, and leaderboard for authenticated users.
Organization context required for leaderboard and levels.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from common.auth.security import OrgMemberRequired, get_current_user
from common.database.client import get_admin_client
from common.schemas.responses import OasisResponse
from services.journey_service.crud import gamification as crud
from services.journey_service.schemas.gamification import (
    ActivityLogEntry,
    LeaderboardEntry,
    LevelInfo,
    PointsHistoryEntry,
    RewardOut,
    UserStats,
)
from supabase import AsyncClient

router = APIRouter()


@router.get(
    "/stats",
    response_model=OasisResponse[UserStats],
    summary="Obtener mis estadísticas",
    description="Obtiene puntos, nivel, progreso y estadísticas del usuario.",
)
async def get_my_stats(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene las estadísticas completas del usuario autenticado:
    - Total de puntos
    - Nivel actual y siguiente
    - Puntos para siguiente nivel
    - Journeys activos y completados
    - Total de actividades
    """
    user_id = UUID(current_user["id"])
    stats = await crud.get_user_stats(db, user_id)

    return OasisResponse(
        success=True,
        message="Estadísticas obtenidas.",
        data=stats,
    )


@router.get(
    "/rewards",
    response_model=OasisResponse[list[RewardOut]],
    summary="Obtener mis recompensas",
    description="Lista las insignias y recompensas obtenidas.",
)
async def get_my_rewards(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    limit: int = Query(50, ge=1, le=100),
):
    """
    Obtiene las recompensas/insignias del usuario autenticado.
    """
    user_id = UUID(current_user["id"])
    rewards = await crud.get_user_rewards(db, user_id, limit)

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(rewards)} recompensas.",
        data=rewards,
    )


@router.get(
    "/activity",
    response_model=OasisResponse[list[ActivityLogEntry]],
    summary="Obtener mi historial de actividades",
    description="Lista las actividades recientes del usuario.",
)
async def get_my_activity(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    limit: int = Query(50, ge=1, le=100),
):
    """
    Obtiene el historial de actividades del usuario.
    """
    user_id = UUID(current_user["id"])
    activities = await crud.get_user_activity_log(db, user_id, limit)

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(activities)} actividades.",
        data=activities,
    )


@router.get(
    "/points-history",
    response_model=OasisResponse[list[PointsHistoryEntry]],
    summary="Obtener historial de puntos",
    description="Lista el historial de puntos ganados/perdidos.",
)
async def get_points_history(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    limit: int = Query(50, ge=1, le=100),
):
    """
    Obtiene el historial de transacciones de puntos del usuario.
    """
    user_id = UUID(current_user["id"])
    history = await crud.get_user_points_history(db, user_id, limit)

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(history)} transacciones.",
        data=history,
    )


@router.get(
    "/leaderboard",
    response_model=OasisResponse[list[LeaderboardEntry]],
    summary="Obtener ranking",
    description="Obtiene el ranking de usuarios por puntos en tu organización.",
)
async def get_leaderboard(
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
    limit: int = Query(20, ge=1, le=100),
):
    """
    Obtiene el ranking de usuarios por puntos totales.

    Requiere header X-Organization-ID para filtrar por organización.
    Solo muestra usuarios de tu misma organización.
    """
    org_id = UUID(ctx["org_id"])
    leaderboard = await crud.get_leaderboard(db, org_id, limit)

    return OasisResponse(
        success=True,
        message=f"Top {len(leaderboard)} usuarios.",
        data=leaderboard,
    )


@router.get(
    "/levels",
    response_model=OasisResponse[list[LevelInfo]],
    summary="Obtener niveles disponibles",
    description="Lista los niveles y sus requisitos de puntos.",
)
async def get_levels(
    ctx: dict = Depends(OrgMemberRequired()),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene los niveles disponibles ordenados por puntos requeridos.

    Requiere header X-Organization-ID para obtener los niveles
    configurados para tu organización.
    """
    org_id = UUID(ctx["org_id"])
    levels = await crud.get_available_levels(db, org_id)

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(levels)} niveles.",
        data=levels,
    )
