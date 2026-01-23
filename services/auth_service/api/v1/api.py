from fastapi import APIRouter

from services.auth_service.api.v1.endpoints import audit, auth, organizations, users

api_router = APIRouter()

# 1. Rutas de Autenticación (Login, Registro, Me)
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# 2. Rutas de Gestión de Usuarios (Admin del sistema)
api_router.include_router(users.router, prefix="/users", tags=["Users"])

# 3. Rutas de Organizaciones (B2B, Membresías)
api_router.include_router(
    organizations.router, prefix="/organizations", tags=["Organizations"]
)

# 4. Rutas de Auditoría (Logs de actividad)
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
