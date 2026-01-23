# common/config.py
from functools import lru_cache

from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# La clase se llama CommonSettings (Correcto)
class CommonSettings(BaseSettings):
    # --- Supabase Core, Auth & Security ---
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    JWT_ALGORITHM: str
    JWT_AUDIENCE: str = "authenticated"
    SUPABASE_JWT_SECRET: str
    SUPABASE_JWKS_URL: str | None = None

    # --- App Metadatos ---

    GOOGLE_API_KEY: str
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Oasis Digital API"
    VERSION: str = "0.0.0"
    DESCRIPTION: str = "Oasis Platform Service"
    BACKEND_CORS_ORIGINS: list[str | AnyHttpUrl] = []

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list | str):
            return v
        raise ValueError(v)


@lru_cache
def get_settings() -> CommonSettings:
    return CommonSettings()


settings = get_settings()
