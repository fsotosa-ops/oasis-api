# common/auth/security.py
import logging

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from common.config import settings
from common.database.client import get_admin_client

security = HTTPBearer()
_jwks_cache = None


async def get_jwks():
    """Obtiene y cachea las llaves públicas de Supabase."""
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(settings.SUPABASE_JWKS_URL, timeout=10)
                response.raise_for_status()
                _jwks_cache = response.json()
            except Exception as err:
                logging.error(f"Error JWKS: {err}")
                raise HTTPException(
                    status_code=503, detail="Error de identidad"
                ) from err
    return _jwks_cache


async def validate_token(
    auth: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> dict:
    """Valida el JWT usando estrategia dinámica (HS256 local / ES256 prod)."""
    token = auth.credentials
    try:
        if settings.JWT_ALGORITHM == "HS256":
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience=settings.JWT_AUDIENCE,
            )
        else:
            jwks = await get_jwks()
            return jwt.decode(
                token, jwks, algorithms=["ES256"], audience=settings.JWT_AUDIENCE
            )
    except JWTError as err:
        raise HTTPException(status_code=401, detail="Token no válido") from err


async def get_current_user(
    payload: dict = Depends(validate_token),  # noqa: B008
) -> dict:
    """Cruza identidad del token con 'profiles' usando el cliente admin."""
    user_id = payload.get("sub")
    db = await get_admin_client()
    try:
        # Se actualizó la selección: 'role' ya no existe, usamos 'is_platform_admin'
        response = (
            await db.table("profiles")
            .select("id, email, is_platform_admin")
            .eq("id", user_id)
            .single()
            .execute()
        )
        return response.data
    except Exception as err:
        logging.error(f"Error al recuperar perfil: {err}")
        raise HTTPException(
            status_code=500, detail="Error al consultar perfil"
        ) from err


class RoleChecker:
    """Verificador de roles con soporte para auditoría Oasis."""

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: dict = Depends(get_current_user)):  # noqa: B008
        # 1. Super Admin de plataforma tiene acceso total
        if user.get("is_platform_admin") is True:
            return user

        # 2. Validación de roles legacy
        # Como 'role' se eliminó de profiles, user.get("role") será None.
        # Esto bloqueará acceso por defecto a menos que se implemente
        # lógica de roles por organización en el endpoint específico.
        user_role = user.get("role")

        if user_role not in self.allowed_roles:
            msg = (
                f"Acceso denegado. Se requiere uno de estos roles: {self.allowed_roles}"
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)
        return user
