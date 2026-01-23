# services/auth_service/core/config.py
from common.config import CommonSettings


class AuthSettings(CommonSettings):
    # --- Sobreescritura de Identidad ---
    PROJECT_NAME: str = "🔐 Auth Service"
    VERSION: str = "1.1.0"
    DESCRIPTION: str = (
        "Servicio de Identidad Multi-Tenant, Gestión de Organizaciones y Seguridad."
    )

    # --- Configuración Única de este Servicio ---
    # Si Auth necesita algo que Event no (ej: expiración de token custom), va aquí
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 días


settings = AuthSettings()
