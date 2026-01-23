# services/auth_service/api/v1/endpoints/audit.py
"""
Audit log endpoints.

Read-only endpoints for viewing audit logs:
- Platform Admins: View all logs
- Org Admins/Owners: View their organization's logs
- Users: View their own activity
"""
from datetime import datetime

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
    get_organization_activity,
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
    admin: dict = Depends(PlatformAdminRequired()),
    db=Depends(get_admin_client),
    skip: int = Query(0, ge=0, description="Records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records"),
    organization_id: str | None = Query(None, description="Filter by organization"),
    user_id: str | None = Query(None, description="Filter by user"),
    category: str | None = Query(None, description="Filter by category code"),
    action: str | None = Query(None, description="Search in action field"),
    start_date: datetime | None = Query(None, description="Start date filter"),
    end_date: datetime | None = Query(None, description="End date filter"),
):
    """
    Lista todos los logs de auditoría.

    Solo accesible por Platform Admins.
    Soporta múltiples filtros para búsqueda avanzada.
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

    except AuditOperationError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


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
    ctx: dict = Depends(OrgRoleChecker(["owner", "admin"])),
    db=Depends(get_supabase_client),
    admin_db=Depends(get_admin_client),
    token: HTTPAuthorizationCredentials = Depends(security),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user_id: str | None = Query(None, description="Filter by user"),
    category: str | None = Query(None, description="Filter by category"),
    action: str | None = Query(None, description="Search in action"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
):
    """
    Lista los logs de auditoría de la organización actual.

    Requiere header X-Organization-ID.
    Accesible por Owners y Admins de la organización.
    """
    org_id = ctx.get("org_id")
    is_platform_admin = ctx.get("org_role") == "platform_admin"

    if not org_id:
        raise HTTPException(
            status_code=400,
            detail="Organization context required. Provide X-Organization-ID header.",
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

    except AuditOperationError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err


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
    current_user: dict = Depends(get_current_user),
    db=Depends(get_supabase_client),
    token: HTTPAuthorizationCredentials = Depends(security),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(50, ge=1, le=200, description="Max records"),
):
    """
    Obtiene tu propia actividad reciente.

    Cualquier usuario autenticado puede ver su historial.
    """
    # RLS asegura que solo vea sus propios logs
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
    current_user: dict = Depends(get_current_user),
    db=Depends(get_supabase_client),
    token: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Lista todas las categorías de auditoría disponibles.

    Útil para filtros en el frontend.
    """
    db.postgrest.auth(token.credentials)

    try:
        categories = await get_audit_categories(db=db)
        return categories

    except AuditOperationError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err
