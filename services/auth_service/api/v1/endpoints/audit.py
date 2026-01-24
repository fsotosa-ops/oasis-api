# services/auth_service/api/v1/endpoints/audit.py
"""
Audit log endpoints.

Read-only endpoints for viewing audit logs:
- Platform Admins: View all logs
- Org Admins/Owners: View their organization's logs
- Users: View their own activity
"""
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from common.auth.security import (
    OrgRoleChecker,
    PlatformAdminRequired,
    get_current_user,
)
from common.database.client import get_admin_client, get_supabase_client
from services.auth_service.crud import (
    AuditOperationError,
    get_audit_categories,
    get_user_activity,
    list_audit_logs,
)
from services.auth_service.schemas.audit import (
    AuditCategoryOut,
    AuditLogOut,
    PaginatedAuditLogsResponse,
)

router = APIRouter()
security = HTTPBearer()


# =============================================================================
# Platform Admin Endpoints
# =============================================================================


@router.get(
    "/logs",
    response_model=PaginatedAuditLogsResponse,
    summary="List all audit logs",
    description="List all audit logs with filters. Platform Admin only.",
)
async def list_all_logs(
    admin: Annotated[dict, Depends(PlatformAdminRequired())],
    db: Annotated[Any, Depends(get_admin_client)],
    skip: Annotated[int, Query(description="Records to skip", ge=0)] = 0,
    limit: Annotated[int, Query(description="Max records", ge=1, le=500)] = 100,
    organization_id: Annotated[
        str | None, Query(description="Filter by organization")
    ] = None,
    user_id: Annotated[str | None, Query(description="Filter by user")] = None,
    category: Annotated[
        str | None, Query(description="Filter by category code")
    ] = None,
    action: Annotated[str | None, Query(description="Search in action field")] = None,
    # Corrección B008 aquí:
    start_date: Annotated[
        datetime | None, Query(description="Start date filter")
    ] = None,
    # Corrección B008 aquí:
    end_date: Annotated[datetime | None, Query(description="End date filter")] = None,
):
    """
    Lista todos los logs de auditoría.
    Solo accesible por Platform Admins.
    """
    try:
        logs, total = await list_audit_logs(
            db=db,
            skip=skip,
            limit=limit,
            organization_id=organization_id,
            user_id=user_id,
            category=category,
            action=action,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "items": logs,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except AuditOperationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Organization Admin Endpoints
# =============================================================================


@router.get(
    "/org",
    response_model=PaginatedAuditLogsResponse,
    summary="Get organization activity",
    description="View audit logs for the current organization context.",
)
async def get_org_logs(
    ctx: Annotated[dict, Depends(OrgRoleChecker(["owner", "admin"]))],
    db: Annotated[Any, Depends(get_supabase_client)],
    admin_db: Annotated[Any, Depends(get_admin_client)],
    token: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    user_id: Annotated[str | None, Query(description="Filter by user")] = None,
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    action: Annotated[str | None, Query(description="Search in action")] = None,
    # Corrección B008 aquí:
    start_date: Annotated[datetime | None, Query()] = None,
    # Corrección B008 aquí:
    end_date: Annotated[datetime | None, Query()] = None,
):
    """
    Lista los logs de auditoría de la organización actual.
    """
    org_id = ctx.get("org_id")
    is_platform_admin = ctx.get("org_role") == "platform_admin"

    if not org_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Organization context required. " "Provide X-Organization-ID header."
            ),
        )

    try:
        if is_platform_admin:
            # Platform Admin usa admin_db
            logs, total = await list_audit_logs(
                db=admin_db,
                skip=skip,
                limit=limit,
                organization_id=org_id,
                user_id=user_id,
                category=category,
                action=action,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            # Org Admin: RLS filtra automáticamente
            db.postgrest.auth(token.credentials)

            logs, total = await list_audit_logs(
                db=db,
                skip=skip,
                limit=limit,
                organization_id=org_id,
                user_id=user_id,
                category=category,
                action=action,
                start_date=start_date,
                end_date=end_date,
            )

        return {
            "items": logs,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except AuditOperationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# User Self-Service Endpoints
# =============================================================================


@router.get(
    "/me",
    response_model=list[AuditLogOut],
    summary="Get my activity",
    description="View your own recent activity log.",
)
async def get_my_activity(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Any, Depends(get_supabase_client)],
    token: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    days: Annotated[int, Query(ge=1, le=365, description="Days to look back")] = 30,
    limit: Annotated[int, Query(ge=1, le=200, description="Max records")] = 50,
):
    """
    Obtiene tu propia actividad reciente.
    """
    db.postgrest.auth(token.credentials)

    try:
        activity = await get_user_activity(
            db=db,
            user_id=current_user["id"],
            days=days,
            limit=limit,
        )

        return activity

    except AuditOperationError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


# =============================================================================
# Reference Data Endpoints
# =============================================================================


@router.get(
    "/categories",
    response_model=list[AuditCategoryOut],
    summary="List audit categories",
    description="Get all available audit log categories.",
)
async def list_categories(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[Any, Depends(get_supabase_client)],
    token: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    """
    Lista todas las categorías de auditoría disponibles.
    """
    db.postgrest.auth(token.credentials)

    try:
        categories = await get_audit_categories(db=db)
        return categories

    except AuditOperationError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
