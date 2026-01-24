# services/auth_service/crud/profiles.py
"""
CRUD operations for user profiles.
Handles all database interactions related to profiles.
"""
import logging
from typing import Any
from uuid import UUID

from supabase import AsyncClient


class ProfileNotFoundError(Exception):
    """Raised when a profile is not found."""

    pass


class ProfileOperationError(Exception):
    """Raised when a profile operation fails."""

    pass


async def get_profile_by_id(
    db: AsyncClient,
    user_id: str | UUID,
) -> dict | None:
    """
    Get a profile by user ID.

    Args:
        db: Supabase client
        user_id: UUID of the user

    Returns:
        Profile dict or None if not found
    """
    try:
        response = (
            await db.table("profiles")
            .select("*")
            .eq("id", str(user_id))
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception as err:
        logging.error(f"Error fetching profile {user_id}: {err}")
        raise ProfileOperationError(f"Error al obtener perfil: {err}") from err


async def get_profile_by_email(
    db: AsyncClient,
    email: str,
) -> dict | None:
    """
    Get a profile by email.

    Args:
        db: Supabase client
        email: User email

    Returns:
        Profile dict or None if not found
    """
    try:
        response = (
            await db.table("profiles").select("*").eq("email", email).limit(1).execute()
        )

        return response.data[0] if response.data else None

    except Exception as err:
        logging.error(f"Error fetching profile by email {email}: {err}")
        raise ProfileOperationError(f"Error al obtener perfil: {err}") from err


async def list_all_profiles(
    db: AsyncClient,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> tuple[list[dict], int]:
    """
    List all profiles with pagination.

    Args:
        db: Supabase client (should be admin client)
        skip: Offset for pagination
        limit: Max results to return
        search: Optional search by email or name

    Returns:
        Tuple of (list of profiles, total count)
    """
    try:
        query = db.table("profiles").select("*", count="exact")

        if search:
            query = query.or_(f"email.ilike.%{search}%,full_name.ilike.%{search}%")

        response = (
            await query.order("created_at", desc=True)
            .range(skip, skip + limit - 1)
            .execute()
        )

        return response.data or [], response.count or 0

    except Exception as err:
        logging.error(f"Error listing profiles: {err}")
        raise ProfileOperationError(f"Error al listar perfiles: {err}") from err


async def update_profile(
    db: AsyncClient,
    user_id: str | UUID,
    update_data: dict[str, Any],
) -> dict:
    """
    Update a profile.

    Args:
        db: Supabase client
        user_id: UUID of the user
        update_data: Fields to update

    Returns:
        Updated profile dict

    Raises:
        ProfileNotFoundError: If profile doesn't exist
    """
    try:
        response = (
            await db.table("profiles")
            .update(update_data)
            .eq("id", str(user_id))
            .execute()
        )

        if not response.data:
            raise ProfileNotFoundError(f"Profile {user_id} not found")

        return response.data[0]

    except ProfileNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error updating profile {user_id}: {err}")
        raise ProfileOperationError(f"Error al actualizar perfil: {err}") from err


async def set_platform_admin_status(
    db: AsyncClient,
    user_id: str | UUID,
    is_admin: bool,
) -> dict:
    """
    Set or remove Platform Admin status for a user.

    Args:
        db: Supabase client (must be admin client)
        user_id: UUID of the user
        is_admin: True to grant, False to revoke

    Returns:
        Updated profile dict

    Raises:
        ProfileNotFoundError: If profile doesn't exist
    """
    try:
        response = (
            await db.table("profiles")
            .update({"is_platform_admin": is_admin})
            .eq("id", str(user_id))
            .execute()
        )

        if not response.data:
            raise ProfileNotFoundError(f"Profile {user_id} not found")

        return response.data[0]

    except ProfileNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error setting admin status for {user_id}: {err}")
        raise ProfileOperationError(f"Error al cambiar estado admin: {err}") from err


async def delete_user_completely(
    db: AsyncClient,
    user_id: str | UUID,
) -> None:
    """
    Delete a user completely from the platform.

    This removes:
    - The user from Supabase Auth
    - Their profile (cascade should handle memberships)

    Args:
        db: Supabase client (must be admin client)
        user_id: UUID of the user to delete

    Raises:
        ProfileNotFoundError: If user doesn't exist
        ProfileOperationError: If deletion fails
    """
    user_id_str = str(user_id)

    try:
        # First verify user exists
        profile = await get_profile_by_id(db, user_id_str)
        if not profile:
            raise ProfileNotFoundError(f"User {user_id_str} not found")

        # Delete from Auth (this should cascade to profile via trigger)
        await db.auth.admin.delete_user(user_id_str)

    except ProfileNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error deleting user {user_id_str}: {err}")
        raise ProfileOperationError(f"Error al eliminar usuario: {err}") from err


async def get_user_with_memberships(
    db: AsyncClient,
    user_id: str | UUID,
) -> dict | None:
    """
    Get a user profile with their organization memberships.

    Args:
        db: Supabase client
        user_id: UUID of the user

    Returns:
        Profile dict with memberships array, or None if not found
    """
    user_id_str = str(user_id)

    try:
        # Get profile
        profile_res = (
            await db.table("profiles")
            .select("*")
            .eq("id", user_id_str)
            .limit(1)
            .execute()
        )

        if not profile_res.data:
            return None

        profile = profile_res.data[0]

        # Get memberships
        memberships_res = (
            await db.table("organization_members")
            .select("role, status, joined_at, organizations(id, name, slug, type)")
            .eq("user_id", user_id_str)
            .execute()
        )

        # Format memberships
        memberships = []
        for m in memberships_res.data or []:
            if m.get("organizations"):
                memberships.append(
                    {
                        "role": m["role"],
                        "status": m["status"],
                        "joined_at": m["joined_at"],
                        "organization": m["organizations"],
                    }
                )

        profile["memberships"] = memberships
        return profile

    except Exception as err:
        logging.error(f"Error fetching user with memberships {user_id_str}: {err}")
        raise ProfileOperationError(f"Error al obtener usuario: {err}") from err
