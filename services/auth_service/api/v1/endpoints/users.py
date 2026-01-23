# services/auth_service/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status

from common.auth.security import RoleChecker
from common.database.client import get_admin_client
from services.auth_service.schemas.users import UserAdminOut, UserPlatformAdminUpdate

router = APIRouter()


@router.patch("/{user_id}/platform-admin", response_model=UserAdminOut)
async def update_platform_admin_status(
    user_id: str,
    update_data: UserPlatformAdminUpdate,
    # Solo el Owner de la plataforma puede nombrar otros Platform Admins
    admin_user: dict = Depends(RoleChecker(["owner"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """Actualiza el privilegio de Administrador de Plataforma (Global)."""
    response = (
        await db.table("profiles")
        .update({"is_platform_admin": update_data.is_platform_admin})
        .eq("id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return response.data[0]


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin_user: dict = Depends(RoleChecker(["owner"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """Elimina permanentemente a un usuario de la plataforma."""
    await db.auth.admin.delete_user(user_id)
    return None


@router.get("/", response_model=list[UserAdminOut])
async def list_all_users(
    admin_user: dict = Depends(RoleChecker(["owner", "admin", "gestor"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """Lista todos los perfiles registrados en la plataforma."""
    response = await db.table("profiles").select("*").execute()
    return response.data
