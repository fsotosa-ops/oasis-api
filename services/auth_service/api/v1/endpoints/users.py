from fastapi import APIRouter, Depends, HTTPException, status

from common.auth.security import RoleChecker
from common.database.client import get_admin_client
from services.auth_service.schemas.users import UserAdminOut, UserPlatformAdminUpdate

router = APIRouter()


@router.patch("/{user_id}/platform-admin", response_model=UserAdminOut)
async def update_platform_admin_status(
    user_id: str,
    update_data: UserPlatformAdminUpdate,
    admin_user: dict = Depends(RoleChecker(["owner"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """
    Promueve o degrada a un usuario como Super Admin de la plataforma.
    """
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
async def delete_user_global(
    user_id: str,
    admin_user: dict = Depends(RoleChecker(["owner"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """
    BORRADO GLOBAL: Elimina al usuario de Auth y Profiles.
    Destruye su acceso a TODAS las organizaciones.
    """
    try:
        await db.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error eliminando usuario: {e}"
        ) from e
    return None


@router.get("/", response_model=list[UserAdminOut])
async def list_all_users(
    admin_user: dict = Depends(RoleChecker(["owner", "admin"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """Lista todos los usuarios de la plataforma (Vista Global)."""
    response = await db.table("profiles").select("*").execute()
    return response.data
