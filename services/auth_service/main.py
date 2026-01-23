from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_settings
from common.database.client import get_admin_client
from services.auth_service.api.v1.api import api_router
from services.auth_service.core.config import settings

global_settings = get_settings()

description_text = """
## 🔐 Oasis Identity & Access Management
Servicio de autenticación Multi-Tenant (B2B/B2C).

### Headers Requeridos
Para operaciones contextuales (dentro de una empresa), enviar:
`X-Organization-ID: <uuid>`
"""

tags_metadata = [
    {"name": "Auth", "description": "Login, Registro y Contexto (/me)"},
    {"name": "Organizations", "description": "Gestión de Empresas y Membresías"},
    {"name": "Users", "description": "Administración de Plataforma"},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_tags=tags_metadata,
    # Configuración de Rutas de Documentación
    openapi_url=f"{global_settings.API_V1_STR}/openapi.json",
    docs_url=f"{global_settings.API_V1_STR}/docs",
    redoc_url=f"{global_settings.API_V1_STR}/redoc",  # <--- AGREGAR ESTA LÍNEA
)

if global_settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in global_settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=global_settings.API_V1_STR)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(response: Response):
    """
    Verifica la salud del servicio y la conexión a la base de datos.
    """
    health_status = {
        "status": "healthy",
        "service": "auth-service",
        "database": "unknown",
    }

    try:
        # Usamos el CLIENTE ADMIN para probar conectividad pura (bypass RLS)
        db = await get_admin_client()

        # Hacemos count='exact' con head=True.
        # Esto verifica que la tabla existe y responde, sin traer datos (muy rápido).
        await db.table("profiles").select("*", count="exact", head=True).execute()

        health_status["database"] = "connected"

    except Exception as e:
        # Si esto falla, realmente la DB está caída o inalcanzable
        health_status["status"] = "unhealthy"
        health_status["database"] = "disconnected"
        health_status["error"] = str(e)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return health_status
