"""
Admin endpoints for Gamification configuration.

Manage levels and rewards/badges for an organization.
Authorization: Requires 'owner' or 'admin' role in the organization.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from common.auth.security import OrgRoleChecker
from common.database.client import get_admin_client
from common.exceptions import ForbiddenError, NotFoundError
from common.schemas.responses import OasisResponse
from services.journey_service.crud import admin as crud
from services.journey_service.schemas.admin import (
    LevelAdminRead,
    LevelCreate,
    LevelUpdate,
    RewardAdminRead,
    RewardCreate,
    RewardUpdate,
)
from supabase import AsyncClient

router = APIRouter()

# Role checker for admin operations
AdminRequired = OrgRoleChecker(["owner", "admin"])


# =============================================================================
# LEVELS ENDPOINTS
# =============================================================================


@router.get(
    "/levels",
    response_model=OasisResponse[list[LevelAdminRead]],
    summary="Listar niveles",
    description="Lista todos los niveles configurados para la organización.",
)
async def list_levels(
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Lista niveles ordenados por puntos mínimos."""
    org_id = ctx["org_id"]

    levels = await crud.list_levels_admin(db, UUID(org_id))

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(levels)} niveles.",
        data=levels,
    )


@router.post(
    "/levels",
    response_model=OasisResponse[LevelAdminRead],
    status_code=status.HTTP_201_CREATED,
    summary="Crear nivel",
    description="Crea un nuevo nivel para la organización.",
)
async def create_level(
    payload: LevelCreate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Crea un nuevo nivel.

    Cada nivel tiene un nombre y puntos mínimos requeridos.
    Los niveles definen la progresión de los usuarios.
    """
    org_id = ctx["org_id"]

    level = await crud.create_level(db, UUID(org_id), payload)
    level["users_at_level"] = 0

    return OasisResponse(
        success=True,
        message="Nivel creado exitosamente.",
        data=level,
    )


@router.put(
    "/levels/{level_id}",
    response_model=OasisResponse[LevelAdminRead],
    summary="Actualizar nivel",
    description="Actualiza la configuración de un nivel.",
)
async def update_level(
    level_id: UUID,
    payload: LevelUpdate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Actualiza un nivel existente."""
    org_id = ctx["org_id"]

    if not await crud.verify_level_ownership(db, level_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este nivel.")

    updated = await crud.update_level(db, level_id, payload)

    if not updated:
        raise NotFoundError("Level", str(level_id))

    updated["users_at_level"] = 0  # Placeholder

    return OasisResponse(
        success=True,
        message="Nivel actualizado exitosamente.",
        data=updated,
    )


@router.delete(
    "/levels/{level_id}",
    response_model=OasisResponse[dict],
    summary="Eliminar nivel",
    description="Elimina un nivel de la organización.",
)
async def delete_level(
    level_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Elimina un nivel.

    NOTA: Los usuarios que tenían este nivel pasarán al nivel inferior.
    """
    org_id = ctx["org_id"]

    if not await crud.verify_level_ownership(db, level_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a este nivel.")

    deleted = await crud.delete_level(db, level_id)

    if not deleted:
        raise NotFoundError("Level", str(level_id))

    return OasisResponse(
        success=True,
        message="Nivel eliminado exitosamente.",
        data={"deleted_id": str(level_id)},
    )


# =============================================================================
# REWARDS ENDPOINTS
# =============================================================================


@router.get(
    "/rewards",
    response_model=OasisResponse[list[RewardAdminRead]],
    summary="Listar recompensas",
    description="Lista todas las recompensas/badges de la organización.",
)
async def list_rewards(
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Lista recompensas con conteo de veces otorgadas."""
    org_id = ctx["org_id"]

    rewards = await crud.list_rewards_admin(db, UUID(org_id))

    return OasisResponse(
        success=True,
        message=f"Se encontraron {len(rewards)} recompensas.",
        data=rewards,
    )


@router.post(
    "/rewards",
    response_model=OasisResponse[RewardAdminRead],
    status_code=status.HTTP_201_CREATED,
    summary="Crear recompensa",
    description="Crea una nueva recompensa/badge para la organización.",
)
async def create_reward(
    payload: RewardCreate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Crea una nueva recompensa.

    Tipos disponibles:
    - 'badge': Insignia visual
    - 'points': Bonus de puntos

    Las condiciones de desbloqueo se configuran en unlock_condition.
    Ejemplo: {"type": "complete_journey", "journey_id": "..."}
    """
    org_id = ctx["org_id"]

    reward = await crud.create_reward(db, UUID(org_id), payload)
    reward["times_awarded"] = 0

    return OasisResponse(
        success=True,
        message="Recompensa creada exitosamente.",
        data=reward,
    )


@router.put(
    "/rewards/{reward_id}",
    response_model=OasisResponse[RewardAdminRead],
    summary="Actualizar recompensa",
    description="Actualiza una recompensa existente.",
)
async def update_reward(
    reward_id: UUID,
    payload: RewardUpdate,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """Actualiza una recompensa."""
    org_id = ctx["org_id"]

    if not await crud.verify_reward_ownership(db, reward_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a esta recompensa.")

    updated = await crud.update_reward(db, reward_id, payload)

    if not updated:
        raise NotFoundError("Reward", str(reward_id))

    # Get times awarded
    updated["times_awarded"] = 0  # Would need to query

    return OasisResponse(
        success=True,
        message="Recompensa actualizada exitosamente.",
        data=updated,
    )


@router.delete(
    "/rewards/{reward_id}",
    response_model=OasisResponse[dict],
    summary="Eliminar recompensa",
    description="Elimina una recompensa del catálogo.",
)
async def delete_reward(
    reward_id: UUID,
    ctx: dict = Depends(AdminRequired),  # noqa: B008
    db: AsyncClient = Depends(get_admin_client),  # noqa: B008
):
    """
    Elimina una recompensa.

    NOTA: Los usuarios que ya obtuvieron esta recompensa la conservan.
    """
    org_id = ctx["org_id"]

    if not await crud.verify_reward_ownership(db, reward_id, UUID(org_id)):
        raise ForbiddenError("No tienes acceso a esta recompensa.")

    deleted = await crud.delete_reward(db, reward_id)

    if not deleted:
        raise NotFoundError("Reward", str(reward_id))

    return OasisResponse(
        success=True,
        message="Recompensa eliminada exitosamente.",
        data={"deleted_id": str(reward_id)},
    )
