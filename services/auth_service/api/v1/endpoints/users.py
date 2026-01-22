# services/auth_service/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, status

from common.auth.security import RoleChecker
from common.database.client import get_admin_client
from common.schemas.auth import ProfileOut

router = APIRouter()


@router.patch("/{user_id}/role", response_model=ProfileOut)
async def update_user_role(
    user_id: str,
    new_role: str,
    admin_user: dict = Depends(RoleChecker(["owner", "admin"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    valid_roles = ["owner", "admin", "gestor", "participante", "visitante"]
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail="Rol no válido")

    response = (
        await db.table("profiles")
        .update({"role": new_role})
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
    # F841: Quitamos el 'res =' porque no se usaba
    await db.auth.admin.delete_user(user_id)
    return None


@router.get("/", response_model=list[ProfileOut])
async def list_all_users(
    admin_user: dict = Depends(RoleChecker(["owner", "admin", "gestor"])),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    response = await db.table("profiles").select("*").execute()
    return response.data
