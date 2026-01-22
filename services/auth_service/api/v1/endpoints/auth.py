from fastapi import APIRouter, Depends

from common.auth.security import get_current_user
from common.schemas.auth import ProfileOut

router = APIRouter()


@router.get("/me", response_model=ProfileOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):  # noqa: B008
    """
    Endpoint protegido: Valida el token JWT y retorna el perfil del usuario.
    Usa la lógica compartida en 'common' para desencriptar y validar.
    """
    return current_user
