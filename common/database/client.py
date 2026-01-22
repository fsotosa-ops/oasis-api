# common/database/client.py
from supabase import AsyncClient, create_async_client

from common.config import get_settings

settings = get_settings()


async def get_supabase_client() -> AsyncClient:
    """Cliente estándar con Anon Key (respeta RLS)."""
    return await create_async_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


async def get_admin_client() -> AsyncClient:
    """
    Retorna un cliente asíncrono usando la nueva Secret Key.
    Se usa para validar perfiles y roles de habitante sin restricciones de RLS.
    """
    return await create_async_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SECRET_KEY,  # Usamos la nueva variable del config.py
    )
