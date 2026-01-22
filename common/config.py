from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Supabase Core ---
    # Se obtienen del dashboard de Supabase (Settings > API)
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SECRET_KEY: str

    # --- Auth & Security (JWK/ES256) ---
    # La URL que proporcionaste para las llaves públicas
    SUPABASE_JWKS_URL: str = (
        "https://lvyplkjrfcqsstnhbytl.supabase.co/auth/v1/.well-known/jwks.json"
    )
    JWT_ALGORITHM: str = "ES256"
    JWT_AUDIENCE: str = "authenticated"

    # --- AI & External Services ---
    GOOGLE_API_KEY: str  # Para el motor de Gemini 1.5 Flash

    # --- App Environment ---
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "OASIS API"
    VERSION: str = "0.1.0"

    # Configuración de Pydantic para leer el archivo .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignora variables adicionales en el .env que no estén aquí
    )


@lru_cache
def get_settings() -> Settings:
    """
    Retorna una instancia cacheada de la configuración.
    El uso de @lru_cache evita leer el archivo .env en cada llamada.
    """
    return Settings()
