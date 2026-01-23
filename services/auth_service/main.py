from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_settings
from common.database.client import get_admin_client
from services.auth_service.api.v1.api import api_router

settings = get_settings()

app = FastAPI(
    title="Oasis Auth Service",
    version=settings.VERSION,
    description="Microservicio encargado de la identidad y perfiles",
)

# Configurar CORS (Vital para que el Frontend Next.js pueda hablar con esto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción cambiar por la URL del frontend real
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir las rutas definidas en api.py
app.include_router(api_router, prefix="/api/v1")


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
