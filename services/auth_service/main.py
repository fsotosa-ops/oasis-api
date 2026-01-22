from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_settings
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


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth-service"}
