# common/database/client.py
"""
Supabase client management with connection pooling.

This module provides singleton instances of Supabase clients to avoid
creating new connections on every request.

Two clients are available:
1. Anon client - Respects RLS policies, used for user-context operations
2. Admin client - Bypasses RLS, used for backend-controlled operations

Usage:
    from common.database.client import get_supabase_client, get_admin_client

    async def my_endpoint(db=Depends(get_supabase_client)):
        # db respects RLS
        ...

    async def admin_endpoint(db=Depends(get_admin_client)):
        # db bypasses RLS - use carefully!
        ...
"""
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from common.config import settings
from supabase import AsyncClient, create_async_client

# ============================================================================
# Singleton Client Instances
# ============================================================================

_supabase_client: AsyncClient | None = None
_admin_client: AsyncClient | None = None
_initialized: bool = False


async def _ensure_clients_initialized():
    """Initialize clients if not already done."""
    global _supabase_client, _admin_client, _initialized

    if _initialized:
        return

    try:
        _supabase_client = await create_async_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY,
        )
        logging.info("Supabase anon client initialized")

        _admin_client = await create_async_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        logging.info("Supabase admin client initialized")

        _initialized = True

    except Exception as err:
        logging.error(f"Failed to initialize Supabase clients: {err}")
        raise


async def get_supabase_client() -> AsyncClient:
    """
    Get the Supabase client with ANON_KEY.

    This client RESPECTS Row Level Security (RLS) policies.
    Use for operations where the user's JWT should determine access.

    Note: For user-context queries, you need to set the auth header:
        db.postgrest.auth(token.credentials)

    Returns:
        AsyncClient: Supabase client instance
    """
    await _ensure_clients_initialized()
    return _supabase_client


async def get_admin_client() -> AsyncClient:
    """
    Get the Supabase client with SERVICE_ROLE_KEY.

    This client BYPASSES Row Level Security (RLS) policies.
    Use for:
    - Backend-controlled operations (invitations, admin tasks)
    - Cross-tenant operations
    - System tasks (cleanup, migrations)

    ⚠️ SECURITY WARNING: Use with caution!
    Only use when the backend has already verified permissions.
    Never expose this client directly to user input.

    Returns:
        AsyncClient: Admin Supabase client instance
    """
    await _ensure_clients_initialized()
    return _admin_client


async def close_db_connections():
    """
    Close all database connections.

    Call this during application shutdown to cleanly release resources.
    """
    global _supabase_client, _admin_client, _initialized

    # Note: supabase-py doesn't have explicit close() yet,
    # but we reset the state for potential reconnection
    _supabase_client = None
    _admin_client = None
    _initialized = False

    logging.info("Database connections closed")


async def health_check() -> dict:
    """
    Check database connectivity.

    Returns:
        dict with 'healthy' boolean and optional 'error' message
    """
    try:
        db = await get_admin_client()
        await db.table("profiles").select("id", count="exact", head=True).execute()
        return {"healthy": True}
    except Exception as err:
        logging.error(f"Database health check failed: {err}")
        return {"healthy": False, "error": str(err)}


# ============================================================================
# Context Manager for Transactional Operations
# ============================================================================


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncClient, None]:
    """
    Context manager for database operations.

    Currently just provides the admin client, but prepared for
    future transaction support when Supabase adds it.

    Usage:
        async with get_db_session() as db:
            await db.table("foo").insert(...)
            await db.table("bar").insert(...)
            # Both succeed or neither
    """
    client = await get_admin_client()
    try:
        yield client
    except Exception as err:
        # When transactions are supported, rollback here
        logging.error(f"Database session error: {err}")
        raise
    finally:
        # When transactions are supported, commit here
        pass


# ============================================================================
# Initialization Check
# ============================================================================


async def verify_connection() -> bool:
    """
    Verify database connection is working.

    Call this during startup to fail fast if DB is unavailable.

    Returns:
        True if connection is healthy

    Raises:
        Exception if connection fails
    """
    result = await health_check()
    if not result["healthy"]:
        raise ConnectionError(f"Database connection failed: {result.get('error')}")
    return True
