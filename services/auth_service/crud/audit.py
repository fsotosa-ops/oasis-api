from supabase import AsyncClient


async def log_user_action(
    db: AsyncClient,
    user_id: str,
    action: str,
    ip_address: str | None,
    user_agent: str | None,
    metadata: dict | None = None,
):
    """Registra un evento en la tabla de auditoría profile_logs."""
    try:
        await db.table("profile_logs").insert(
            {
                "user_id": user_id,
                "category_code": "auth",
                "action_code": action,
                "metadata": metadata or {},
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
        ).execute()
    except Exception as e:
        # En producción, aquí deberías usar un logger real (ej: Sentry)
        print(f"Error escribiendo log de auditoría: {e}")
