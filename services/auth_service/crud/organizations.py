# services/auth_service/crud/organizations.py
"""
CRUD operations for organizations and memberships.
Handles all database interactions related to organizations and their members.
"""
import logging
from typing import Any
from uuid import UUID

from supabase import AsyncClient

# ============================================================================
# Exceptions
# ============================================================================


class OrganizationNotFoundError(Exception):
    """Raised when an organization is not found."""

    pass


class OrganizationExistsError(Exception):
    """Raised when trying to create an organization that already exists."""

    pass


class OrganizationOperationError(Exception):
    """Raised when an organization operation fails."""

    pass


class MembershipNotFoundError(Exception):
    """Raised when a membership is not found."""

    pass


class MembershipExistsError(Exception):
    """Raised when a membership already exists."""

    pass


class MembershipOperationError(Exception):
    """Raised when a membership operation fails."""

    pass


# ============================================================================
# Organization Operations
# ============================================================================


async def get_organization_by_id(
    db: AsyncClient,
    org_id: str | UUID,
) -> dict | None:
    """
    Get an organization by ID.

    Args:
        db: Supabase client
        org_id: UUID of the organization

    Returns:
        Organization dict or None if not found
    """
    try:
        response = (
            await db.table("organizations")
            .select("*")
            .eq("id", str(org_id))
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception as err:
        logging.error(f"Error fetching organization {org_id}: {err}")
        raise OrganizationOperationError(
            f"Error al obtener organización: {err}"
        ) from err


async def get_organization_by_slug(
    db: AsyncClient,
    slug: str,
) -> dict | None:
    """
    Get an organization by slug.

    Args:
        db: Supabase client
        slug: Organization slug

    Returns:
        Organization dict or None if not found
    """
    try:
        response = (
            await db.table("organizations")
            .select("*")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception as err:
        logging.error(f"Error fetching organization by slug {slug}: {err}")
        raise OrganizationOperationError(
            f"Error al obtener organización: {err}"
        ) from err


async def list_all_organizations(
    db: AsyncClient,
    skip: int = 0,
    limit: int = 100,
    org_type: str | None = None,
) -> tuple[list[dict], int]:
    """
    List all organizations with pagination.

    Args:
        db: Supabase client (should be admin client)
        skip: Offset for pagination
        limit: Max results to return
        org_type: Optional filter by organization type

    Returns:
        Tuple of (list of organizations, total count)
    """
    try:
        query = db.table("organizations").select("*", count="exact")

        if org_type:
            query = query.eq("type", org_type)

        response = (
            await query.order("created_at", desc=True)
            .range(skip, skip + limit - 1)
            .execute()
        )

        return response.data or [], response.count or 0

    except Exception as err:
        logging.error(f"Error listing organizations: {err}")
        raise OrganizationOperationError(
            f"Error al listar organizaciones: {err}"
        ) from err


async def list_user_organizations(
    db: AsyncClient,
    user_id: str | UUID,
    status: str = "active",
) -> list[dict]:
    """
    List organizations where a user is a member.

    Args:
        db: Supabase client
        user_id: UUID of the user
        status: Membership status filter (default: active)

    Returns:
        List of organizations with membership info
    """
    try:
        response = (
            await db.table("organization_members")
            .select("role, status, joined_at, organizations(*)")
            .eq("user_id", str(user_id))
            .eq("status", status)
            .execute()
        )

        orgs = []
        for item in response.data or []:
            if item.get("organizations"):
                orgs.append(
                    {
                        **item["organizations"],
                        "membership_role": item["role"],
                        "membership_status": item["status"],
                        "joined_at": item["joined_at"],
                    }
                )

        return orgs

    except Exception as err:
        logging.error(f"Error listing user organizations for {user_id}: {err}")
        raise OrganizationOperationError(
            f"Error al listar organizaciones: {err}"
        ) from err


async def create_organization(
    db: AsyncClient,
    name: str,
    slug: str,
    org_type: str = "standard",
    settings: dict[str, Any] | None = None,
    owner_id: str | UUID | None = None,
) -> dict:
    """
    Create a new organization.

    Args:
        db: Supabase client (should be admin client)
        name: Organization name
        slug: URL-friendly identifier
        org_type: Organization type (community, standard, enterprise)
        settings: Optional settings dict
        owner_id: Optional owner to add as first member

    Returns:
        Created organization dict

    Raises:
        OrganizationExistsError: If slug already exists
    """
    try:
        # Check if slug exists
        existing = await get_organization_by_slug(db, slug)
        if existing:
            raise OrganizationExistsError(
                f"Organization with slug '{slug}' already exists"
            )

        # Create organization
        response = (
            await db.table("organizations")
            .insert(
                {
                    "name": name,
                    "slug": slug,
                    "type": org_type,
                    "settings": settings or {},
                }
            )
            .execute()
        )

        if not response.data:
            raise OrganizationOperationError("Failed to create organization")

        org = response.data[0]

        # Add owner if provided
        if owner_id:
            await add_member(db, org["id"], owner_id, role="owner")

        return org

    except (OrganizationExistsError, OrganizationOperationError):
        raise
    except Exception as err:
        logging.error(f"Error creating organization: {err}")
        raise OrganizationOperationError(f"Error al crear organización: {err}") from err


async def update_organization(
    db: AsyncClient,
    org_id: str | UUID,
    update_data: dict[str, Any],
) -> dict:
    """
    Update an organization.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        update_data: Fields to update

    Returns:
        Updated organization dict

    Raises:
        OrganizationNotFoundError: If organization doesn't exist
    """
    try:
        response = (
            await db.table("organizations")
            .update(update_data)
            .eq("id", str(org_id))
            .execute()
        )

        if not response.data:
            raise OrganizationNotFoundError(f"Organization {org_id} not found")

        return response.data[0]

    except OrganizationNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error updating organization {org_id}: {err}")
        raise OrganizationOperationError(
            f"Error al actualizar organización: {err}"
        ) from err


async def delete_organization(
    db: AsyncClient,
    org_id: str | UUID,
) -> None:
    """
    Delete an organization.

    Args:
        db: Supabase client (should be admin client)
        org_id: UUID of the organization

    Raises:
        OrganizationNotFoundError: If organization doesn't exist
    """
    try:
        response = (
            await db.table("organizations").delete().eq("id", str(org_id)).execute()
        )

        if not response.data:
            raise OrganizationNotFoundError(f"Organization {org_id} not found")

    except OrganizationNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error deleting organization {org_id}: {err}")
        raise OrganizationOperationError(
            f"Error al eliminar organización: {err}"
        ) from err


# ============================================================================
# Membership Operations
# ============================================================================


async def get_membership(
    db: AsyncClient,
    org_id: str | UUID,
    user_id: str | UUID,
) -> dict | None:
    """
    Get a specific membership.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        user_id: UUID of the user

    Returns:
        Membership dict or None if not found
    """
    try:
        response = (
            await db.table("organization_members")
            .select("*")
            .eq("organization_id", str(org_id))
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception as err:
        logging.error(f"Error fetching membership: {err}")
        raise MembershipOperationError(f"Error al obtener membresía: {err}") from err


async def list_organization_members(
    db: AsyncClient,
    org_id: str | UUID,
    status: str | None = None,
    role: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[dict], int]:
    """
    List members of an organization.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        status: Optional status filter
        role: Optional role filter
        skip: Offset for pagination
        limit: Max results to return

    Returns:
        Tuple of (list of members with user info, total count)
    """
    try:
        query = (
            db.table("organization_members")
            .select(
                "id, role, status, joined_at, user_id, "
                "profiles(id, email, full_name, avatar_url)",
                count="exact",
            )
            .eq("organization_id", str(org_id))
        )

        if status:
            query = query.eq("status", status)
        if role:
            query = query.eq("role", role)

        response = (
            await query.order("joined_at", desc=True)
            .range(skip, skip + limit - 1)
            .execute()
        )

        members = []
        for m in response.data or []:
            members.append(
                {
                    "id": m["id"],
                    "user_id": m["user_id"],
                    "role": m["role"],
                    "status": m["status"],
                    "joined_at": m["joined_at"],
                    "user": m.get("profiles"),
                }
            )

        return members, response.count or 0

    except Exception as err:
        logging.error(f"Error listing organization members for {org_id}: {err}")
        raise MembershipOperationError(f"Error al listar miembros: {err}") from err


async def add_member(
    db: AsyncClient,
    org_id: str | UUID,
    user_id: str | UUID,
    role: str = "member",
    status: str = "active",
) -> dict:
    """
    Add a member to an organization.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        user_id: UUID of the user
        role: Member role (owner, admin, facilitador, member)
        status: Membership status (active, invited, suspended)

    Returns:
        Created membership dict

    Raises:
        MembershipExistsError: If user is already a member
    """
    try:
        # Check if already a member
        existing = await get_membership(db, org_id, user_id)
        if existing:
            raise MembershipExistsError("User is already a member of this organization")

        response = (
            await db.table("organization_members")
            .insert(
                {
                    "organization_id": str(org_id),
                    "user_id": str(user_id),
                    "role": role,
                    "status": status,
                }
            )
            .execute()
        )

        if not response.data:
            raise MembershipOperationError("Failed to add member")

        return response.data[0]

    except MembershipExistsError:
        raise
    except Exception as err:
        logging.error(f"Error adding member to {org_id}: {err}")
        raise MembershipOperationError(f"Error al agregar miembro: {err}") from err


async def update_membership(
    db: AsyncClient,
    org_id: str | UUID,
    user_id: str | UUID,
    update_data: dict[str, Any],
) -> dict:
    """
    Update a membership.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        user_id: UUID of the user
        update_data: Fields to update (role, status)

    Returns:
        Updated membership dict

    Raises:
        MembershipNotFoundError: If membership doesn't exist
    """
    try:
        response = (
            await db.table("organization_members")
            .update(update_data)
            .eq("organization_id", str(org_id))
            .eq("user_id", str(user_id))
            .execute()
        )

        if not response.data:
            raise MembershipNotFoundError("Membership not found")

        return response.data[0]

    except MembershipNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error updating membership: {err}")
        raise MembershipOperationError(f"Error al actualizar membresía: {err}") from err


async def remove_member(
    db: AsyncClient,
    org_id: str | UUID,
    user_id: str | UUID,
) -> None:
    """
    Remove a member from an organization.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        user_id: UUID of the user

    Raises:
        MembershipNotFoundError: If membership doesn't exist
    """
    try:
        response = (
            await db.table("organization_members")
            .delete()
            .eq("organization_id", str(org_id))
            .eq("user_id", str(user_id))
            .execute()
        )

        if not response.data:
            raise MembershipNotFoundError("Membership not found")

    except MembershipNotFoundError:
        raise
    except Exception as err:
        logging.error(f"Error removing member from {org_id}: {err}")
        raise MembershipOperationError(f"Error al remover miembro: {err}") from err


async def count_owners(
    db: AsyncClient,
    org_id: str | UUID,
) -> int:
    """
    Count the number of owners in an organization.

    Args:
        db: Supabase client
        org_id: UUID of the organization

    Returns:
        Number of owners
    """
    try:
        response = (
            await db.table("organization_members")
            .select("id", count="exact")
            .eq("organization_id", str(org_id))
            .eq("role", "owner")
            .eq("status", "active")
            .execute()
        )

        return response.count or 0

    except Exception as err:
        logging.error(f"Error counting owners for {org_id}: {err}")
        raise MembershipOperationError(f"Error al contar owners: {err}") from err


async def transfer_ownership(
    db: AsyncClient,
    org_id: str | UUID,
    from_user_id: str | UUID,
    to_user_id: str | UUID,
) -> tuple[dict, dict]:
    """
    Transfer ownership from one user to another.

    Args:
        db: Supabase client
        org_id: UUID of the organization
        from_user_id: Current owner's UUID
        to_user_id: New owner's UUID

    Returns:
        Tuple of (old owner membership, new owner membership)

    Raises:
        MembershipNotFoundError: If either membership doesn't exist
        MembershipOperationError: If transfer fails
    """
    org_id_str = str(org_id)
    from_id_str = str(from_user_id)
    to_id_str = str(to_user_id)

    try:
        # Verify current owner
        from_membership = await get_membership(db, org_id_str, from_id_str)
        if not from_membership or from_membership["role"] != "owner":
            raise MembershipOperationError("Source user is not an owner")

        # Verify target is a member
        to_membership = await get_membership(db, org_id_str, to_id_str)
        if not to_membership:
            raise MembershipNotFoundError("Target user is not a member")

        # Demote old owner to admin
        old_owner = await update_membership(
            db, org_id_str, from_id_str, {"role": "admin"}
        )

        # Promote new owner
        new_owner = await update_membership(
            db, org_id_str, to_id_str, {"role": "owner"}
        )

        return old_owner, new_owner

    except (MembershipNotFoundError, MembershipOperationError):
        raise
    except Exception as err:
        logging.error(f"Error transferring ownership in {org_id}: {err}")
        raise MembershipOperationError(f"Error al transferir ownership: {err}") from err
