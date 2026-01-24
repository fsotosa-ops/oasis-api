# services/auth_service/api/v1/endpoints/users.py
"""
User management endpoints.

This module provides two levels of user management:
1. Platform Admin operations - Global management of all users
2. Organization Admin operations - Management within organization context

Security: Defense in depth
- Backend validates permissions
- RLS acts as second layer
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.auth.security import (
    OrgRoleChecker,
    PlatformAdminRequired,
    can_manage_role,
    get_current_user,
)
from common.database.client import get_admin_client, get_supabase_client
from services.auth_service.crud import (
    ProfileNotFoundError,
    ProfileOperationError,
    delete_user_completely,
    get_membership,
    get_user_with_memberships,
    list_all_profiles,
    list_organization_members,
    remove_member,
    set_platform_admin_status,
)
from services.auth_service.schemas.users import (
    PaginatedUsersResponse,
    UserAdminOut,
    UserDetailOut,
    UserPlatformAdminUpdate,
)

router = APIRouter()
security = HTTPBearer()


# ============================================================================
# Platform Admin Operations (Global) - Usan admin_db (bypass RLS)
# ============================================================================


@router.get(
    "/",
    response_model=PaginatedUsersResponse,
    summary="List all platform users",
    description="List all users in the platform. Platform Admin only.",
)
async def list_all_users(
    admin: dict = Depends(PlatformAdminRequired()),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
    skip: int = Query(0, ge=0, description="Number of records to skip"),  # noqa: B008
    limit: int = Query(
        100, ge=1, le=500, description="Max records to return"
    ),  # noqa: B008
    search: str | None = Query(
        None, description="Search by email or name"
    ),  # noqa: B008
):
    """
    Lista todos los usuarios de la plataforma.
    Solo accesible por Platform Admins - usa admin_db (bypass RLS).
    """
    try:
        users, total = await list_all_profiles(
            db=db,
            skip=skip,
            limit=limit,
            search=search,
        )

        return {
            "items": users,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except ProfileOperationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/{user_id}",
    response_model=UserDetailOut,
    summary="Get user details",
    description=(
        "Get detailed user information including memberships." "Platform Admin only."
    ),
)
async def get_user_details(
    user_id: str,
    admin: dict = Depends(PlatformAdminRequired()),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """
    Obtiene detalles completos de un usuario incluyendo sus membresías.
    Solo accesible por Platform Admins.
    """
    try:
        user = await get_user_with_memberships(db=db, user_id=user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user

    except ProfileOperationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch(
    "/{user_id}/platform-admin",
    response_model=UserAdminOut,
    summary="Set platform admin status",
    description=("Promote or demote a user as Platform Admin." "Platform Admin only."),
)
async def update_platform_admin_status(
    user_id: str,
    update_data: UserPlatformAdminUpdate,
    admin: dict = Depends(PlatformAdminRequired()),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """
    Promueve o degrada a un usuario como Platform Admin.

    Restricciones:
    - No puedes degradarte a ti mismo
    - Solo Platform Admins pueden hacer esto
    """
    # Prevent self-demotion
    if user_id == admin["id"] and not update_data.is_platform_admin:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove your own Platform Admin status",
        )

    try:
        updated_user = await set_platform_admin_status(
            db=db,
            user_id=user_id,
            is_admin=update_data.is_platform_admin,
        )
        return updated_user

    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ProfileOperationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user globally",
    description="Permanently delete a user from the platform. Platform Admin only.",
)
async def delete_user_global(
    user_id: str,
    admin: dict = Depends(PlatformAdminRequired()),  # noqa: B008
    db=Depends(get_admin_client),  # noqa: B008
):
    """
    Elimina un usuario completamente de la plataforma.

    ADVERTENCIA: Esta acción es irreversible.
    Elimina el usuario de Auth, su perfil, y todas sus membresías.

    Restricciones:
    - No puedes eliminarte a ti mismo
    """
    # Prevent self-deletion
    if user_id == admin["id"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account from this endpoint",
        )

    try:
        await delete_user_completely(db=db, user_id=user_id)
        return None

    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ProfileOperationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ============================================================================
# Organization Admin Operations (Contextual) - Defensa en profundidad
# ============================================================================


@router.get(
    "/org/members",
    response_model=PaginatedUsersResponse,
    summary="List organization members",
    description="List members of the current organization context.",
)
async def list_org_members(
    ctx: Annotated[
        dict, Depends(OrgRoleChecker(["owner", "admin", "facilitador"]))  # noqa: B008
    ],  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    skip: int = Query(0, ge=0),  # noqa: B008
    limit: int = Query(100, ge=1, le=500),  # noqa: B008
    role: str | None = Query(None, description="Filter by role"),  # noqa: B008
    status_filter: str | None = Query(  # noqa: B008
        None, alias="status", description="Filter by status"
    ),
):
    """
    Lista los miembros de la organización actual.

    Requiere el header X-Organization-ID.
    Accesible por owners, admins y facilitadores.

    Defensa en profundidad:
    - Backend verifica rol via OrgRoleChecker
    - RLS verifica acceso a organization_members
    """
    org_id = ctx["org_id"]
    is_platform_admin = ctx.get("org_role") == "platform_admin"

    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Organization context required. Provide X-Organization-ID header.",
        )

    if is_platform_admin:
        # Platform Admin usa admin_db
        members, total = await list_organization_members(
            db=admin_db,
            org_id=org_id,
            status=status_filter,
            role=role,
            skip=skip,
            limit=limit,
        )
    else:
        # Usuario normal: RLS como segunda capa
        db.postgrest.auth(token.credentials)

        try:
            query = (
                db.table("organization_members")
                .select(
                    "id, role, status, joined_at, user_id, "
                    "profiles(id, email, full_name, avatar_url)",
                    count="exact",
                )
                .eq("organization_id", org_id)
            )

            if status_filter:
                query = query.eq("status", status_filter)
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

            total = response.count or 0

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    # Flatten for response
    items = []
    for m in members:
        user_data = m.get("user") or {}
        items.append(
            {
                **user_data,
                "org_role": m["role"],
                "membership_status": m["status"],
                "joined_at": m["joined_at"],
            }
        )

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.delete(
    "/org/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member from organization",
    description=(
        "Remove a user from the current organization." "Does not delete their account."
    ),
)
async def remove_org_member(
    user_id: str,
    ctx: dict = Depends(OrgRoleChecker(["owner", "admin"])),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    admin_db=Depends(get_admin_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
):
    """
    Remueve a un usuario de la organización actual.

    NO elimina su cuenta - solo la membresía en esta organización.

    Defensa en profundidad:
    - Backend verifica permisos via OrgRoleChecker
    - Backend verifica jerarquía de roles
    - RLS verifica permiso DELETE
    """
    org_id = ctx["org_id"]
    requester_id = ctx["id"]
    requester_role = ctx["org_role"]
    is_platform_admin = requester_role == "platform_admin"

    # Can't remove yourself via this endpoint
    if user_id == requester_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove yourself. Use the organization members endpoint.",
        )

    # Get target's membership
    target_membership = await get_membership(admin_db, org_id, user_id)

    if not target_membership:
        raise HTTPException(
            status_code=404, detail="User is not a member of this organization"
        )

    # Check hierarchy
    if not can_manage_role(requester_role, target_membership["role"]):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Cannot remove a {target_membership['role']}."
                "Insufficient permissions."
            ),
        )

    try:
        if is_platform_admin:
            await remove_member(db=admin_db, org_id=org_id, user_id=user_id)
        else:
            # RLS como segunda capa
            db.postgrest.auth(token.credentials)

            response = (
                await db.table("organization_members")
                .delete()
                .eq("organization_id", org_id)
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data:
                raise HTTPException(
                    status_code=404, detail="Member not found or no permission"
                )

        return None

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================================
# Self-service Operations (Any authenticated user)
# ============================================================================


@router.get(
    "/me/organizations",
    summary="Get my organizations",
    description="Get list of organizations where the current user is a member.",
)
async def get_my_organizations(
    current_user: dict = Depends(get_current_user),  # noqa: B008
    db=Depends(get_supabase_client),  # noqa: B008
    token: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
):
    """
    Obtiene las organizaciones donde el usuario actual es miembro.

    Defensa en profundidad:
    - Backend filtra por user_id
    - RLS verifica acceso
    """
    # RLS como segunda capa
    db.postgrest.auth(token.credentials)

    try:
        response = (
            await db.table("organization_members")
            .select("role, status, joined_at, organizations(*)")
            .eq("user_id", current_user["id"])
            .eq("status", "active")
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
