# common/database/client.py
from common.config import settings
from supabase import AsyncClient, create_async_client


async def get_supabase_client() -> AsyncClient:
    return await create_async_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


async def get_admin_client() -> AsyncClient:
    """Bypassa RLS usando SERVICE_ROLE_KEY."""
    return await create_async_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
