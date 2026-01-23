from typing import Any

from common.schemas.logs import LogCategory
from supabase import AsyncClient


async def log_user_action(
    db: AsyncClient,
    user_id: str,
    action: str,
    category: LogCategory,
    organization_id: str | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
):
    """
    Registra un evento en la tabla audit.logs soportando Multi-Tenancy.
    """
    try:
        # 1. Obtener email (Snapshot para auditoría)
        actor_email = None
        if user_id:
            # Nota: Usamos table("profiles") directo porque está en esquema public (default)
            try:
                res = (
                    await db.table("profiles")
                    .select("email")
                    .eq("id", user_id)
                    .single()
                    .execute()
                )
                if res.data:
                    actor_email = res.data.get("email")
            except Exception:
                pass

        payload = {
            "actor_id": user_id,
            "actor_email": actor_email,
            "organization_id": organization_id,
            "category_code": category.value,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        await db.schema("audit").from_("logs").insert(payload).execute()

    except Exception as e:
        print(f"❌ Error escribiendo Audit Log: {str(e)}")
