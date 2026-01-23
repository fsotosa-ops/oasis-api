# services/auth_service/api/v1/endpoints/auth.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common.auth.security import get_current_user
from common.database.client import get_supabase_client
from common.schemas.auth import ProfileOut

router = APIRouter()


class LoginCredentials(BaseModel):
    email: str
    password: str


@router.get("/me", response_model=ProfileOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):  # noqa: B008
    """Retorna el perfil del habitante actualmente autenticado."""
    return current_user


@router.post("/login")
async def login(
    credentials: LoginCredentials, db=Depends(get_supabase_client)  # noqa: B008
):
    """Punto único de acceso para habitantes de Oasis."""
    try:
        return await db.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )
    except Exception as err:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas") from err
