# common/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Supabase Core ---
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # --- Auth & Security ---
    JWT_ALGORITHM: str
    JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_SECRET: str
    SUPABASE_JWKS_URL: str | None = None

    # --- App Metadatos ---
    GOOGLE_API_KEY: str
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "OASIS API"
    VERSION: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
