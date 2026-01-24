# services/auth_service/crud/audit.py
"""
CRUD operations for audit logs.
Handles all database interactions related to audit logging.
"""
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from common.schemas.logs import LogCategory
from supabase import AsyncClient


class AuditOperationError(Exception):
    """Raised when an audit operation fails."""

    pass


async def log_user_action(
    db: AsyncClient,
    user_id: str | UUID,
    action: str,
    category: LogCategory,
    organization_id: str | UUID | None = None,
    resource: str | None = None,
    resource_id: str | UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict | None:
    """
    Registra un evento en la tabla audit.logs.

    Args:
        db: Cliente de Supabase (debe ser admin client)
        user_id: UUID del actor
        action: Acción realizada (LOGIN, LOGOUT, CREATE_ORG, etc.)
        category: Categoría del log
        organization_id: Contexto de organización (opcional)
        resource: Tipo de recurso afectado
        resource_id: ID del recurso afectado
        metadata: Datos adicionales
        ip_address: IP del cliente
        user_agent: User-Agent del cliente

    Returns:
        Log creado o None si falló
    """
    try:
        # Obtener email para snapshot
        actor_email = None
        if user_id:
            try:
                res = (
                    await db.table("profiles")
                    .select("email")
                    .eq("id", str(user_id))
                    .limit(1)
                    .execute()
                )
                if res.data:
                    actor_email = res.data[0].get("email")
            except Exception:
                pass

        payload = {
            "actor_id": str(user_id) if user_id else None,
            "actor_email": actor_email,
            "organization_id": str(organization_id) if organization_id else None,
            "category_code": category.value,
            "action": action,
            "resource": resource,
            "resource_id": str(resource_id) if resource_id else None,
            "metadata": metadata or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        response = await db.schema("audit").from_("logs").insert(payload).execute()

        return response.data[0] if response.data else None

    except Exception as e:
        # No propagamos el error para no interrumpir el flujo principal
        logging.error(f"Error writing audit log: {str(e)}")
        return None


async def list_audit_logs(
    db: AsyncClient,
    skip: int = 0,
    limit: int = 100,
    organization_id: str | UUID | None = None,
    user_id: str | UUID | None = None,
    category: str | None = None,
    action: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[dict], int]:
    """
    Lista logs de auditoría con filtros.
    Solo accesible por Platform Admins o Org Admins (según RLS).

    Args:
        db: Cliente de Supabase
        skip: Offset para paginación
        limit: Límite de resultados
        organization_id: Filtrar por organización
        user_id: Filtrar por usuario
        category: Filtrar por categoría
        action: Filtrar por acción
        start_date: Fecha inicio
        end_date: Fecha fin

    Returns:
        Tupla de (lista de logs, total count)
    """
    try:
        query = db.schema("audit").from_("logs").select("*", count="exact")

        if organization_id:
            query = query.eq("organization_id", str(organization_id))
        if user_id:
            query = query.eq("actor_id", str(user_id))
        if category:
            query = query.eq("category_code", category)
        if action:
            query = query.ilike("action", f"%{action}%")
        if start_date:
            query = query.gte("occurred_at", start_date.isoformat())
        if end_date:
            query = query.lte("occurred_at", end_date.isoformat())

        response = (
            await query.order("occurred_at", desc=True)
            .range(skip, skip + limit - 1)
            .execute()
        )

        return response.data or [], response.count or 0

    except Exception as err:
        logging.error(f"Error listing audit logs: {err}")
        raise AuditOperationError(f"Error al listar logs: {err}") from err


async def get_user_activity(
    db: AsyncClient,
    user_id: str | UUID,
    days: int = 30,
    limit: int = 50,
) -> list[dict]:
    """
    Obtiene la actividad reciente de un usuario.

    Args:
        db: Cliente de Supabase
        user_id: UUID del usuario
        days: Número de días hacia atrás
        limit: Límite de resultados

    Returns:
        Lista de actividades
    """
    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        response = (
            await db.schema("audit")
            .from_("logs")
            .select("*")
            .eq("actor_id", str(user_id))
            .gte("occurred_at", cutoff_date.isoformat())
            .order("occurred_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data or []

    except Exception as err:
        logging.error(f"Error fetching user activity for {user_id}: {err}")
        raise AuditOperationError(f"Error al obtener actividad: {err}") from err


async def get_organization_activity(
    db: AsyncClient,
    organization_id: str | UUID,
    days: int = 30,
    limit: int = 100,
) -> list[dict]:
    """
    Obtiene la actividad reciente de una organización.

    Args:
        db: Cliente de Supabase
        organization_id: UUID de la organización
        days: Número de días hacia atrás
        limit: Límite de resultados

    Returns:
        Lista de actividades
    """
    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        response = (
            await db.schema("audit")
            .from_("logs")
            .select("*")
            .eq("organization_id", str(organization_id))
            .gte("occurred_at", cutoff_date.isoformat())
            .order("occurred_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data or []

    except Exception as err:
        logging.error(f"Error fetching org activity for {organization_id}: {err}")
        raise AuditOperationError(f"Error al obtener actividad: {err}") from err


async def get_audit_categories(db: AsyncClient) -> list[dict]:
    """
    Obtiene todas las categorías de auditoría disponibles.

    Args:
        db: Cliente de Supabase

    Returns:
        Lista de categorías
    """
    try:
        response = (
            await db.schema("audit")
            .from_("categories")
            .select("*")
            .order("code")
            .execute()
        )

        return response.data or []

    except Exception as err:
        logging.error(f"Error fetching audit categories: {err}")
        raise AuditOperationError(f"Error al obtener categorías: {err}") from err
