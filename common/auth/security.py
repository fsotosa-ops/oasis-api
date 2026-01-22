import logging

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from common.config import get_settings
from common.database.client import get_admin_client

settings = get_settings()
security = HTTPBearer()

_jwks_cache = None


async def get_jwks():
    """Obtiene y cachea las llaves públicas de Supabase para ES256."""
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(settings.SUPABASE_JWKS_URL, timeout=10)
                response.raise_for_status()
                _jwks_cache = response.json()
            except Exception as err:
                logging.error(f"Error obteniendo JWKS: {err}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Error de validación con el servidor de identidad",
                ) from err
    return _jwks_cache


async def validate_token(
    auth: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> dict:
    """Valida el JWT usando el algoritmo ES256 y la curva P-256."""
    token = auth.credentials
    jwks = await get_jwks()

    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            options={"verify_sub": True},
        )
        return payload
    except JWTError as err:
        logging.warning(f"Fallo en validación de token: {err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido, expirado o firma no reconocida",
        ) from err


async def get_current_user(
    payload: dict = Depends(validate_token),  # noqa: B008
) -> dict:
    """Cruza la identidad del token con 'profiles' para obtener el rol."""
    user_id = payload.get("sub")
    db = await get_admin_client()

    try:
        response = (
            await db.table("profiles")
            .select("id, email, role")
            .eq("id", user_id)
            .single()
            .execute()
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al consultar el perfil del habitante",
        ) from err

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El perfil del habitante no existe",
        )

    return response.data
