"""
Webhook Service Configuration

Centralizes all provider secrets and service settings.
Provider secrets are accessed via get_secret(provider_name) for consistency.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings

from common.config import CommonSettings


class ProviderSecrets(BaseSettings):
    """
    Centralized secrets for all webhook providers.

    Add new provider secrets here. The naming convention is:
    WEBHOOK_{PROVIDER}_SECRET for consistency.
    """

    # Provider secrets (empty string = not configured)
    WEBHOOK_TYPEFORM_SECRET: str = ""
    WEBHOOK_STRIPE_SECRET: str = ""
    WEBHOOK_ZOOM_SECRET: str = ""
    WEBHOOK_GITHUB_SECRET: str = ""

    # Mapping of provider names to their secret attribute names
    _SECRET_MAPPING: dict[str, str] = {
        "typeform": "WEBHOOK_TYPEFORM_SECRET",
        "stripe": "WEBHOOK_STRIPE_SECRET",
        "zoom": "WEBHOOK_ZOOM_SECRET",
        "github": "WEBHOOK_GITHUB_SECRET",
    }

    def get_secret(self, provider: str) -> str | None:
        """
        Get the secret for a provider by name.

        Args:
            provider: Provider name (e.g., 'typeform', 'stripe')

        Returns:
            The secret string, or None if not configured
        """
        attr_name = self._SECRET_MAPPING.get(provider.lower())
        if not attr_name:
            return None

        value = getattr(self, attr_name, None)
        return value if value else None

    def has_secret(self, provider: str) -> bool:
        """Check if a provider has a configured secret."""
        secret = self.get_secret(provider)
        return bool(secret)

    def list_configured_providers(self) -> list[str]:
        """List all providers that have configured secrets."""
        return [name for name in self._SECRET_MAPPING if self.has_secret(name)]

    class Config:
        env_file = ".env"
        extra = "ignore"


class WebhookSettings(CommonSettings):
    """
    Webhook Service settings.

    Inherits common settings and adds webhook-specific configuration.
    """

    # Service identification
    PROJECT_NAME: str = "OASIS Webhook Service"

    # Journey service connection
    JOURNEY_SERVICE_URL: str = "http://localhost:8002"
    SERVICE_TO_SERVICE_TOKEN: str = ""

    # Provider secrets (nested for organization)
    secrets: ProviderSecrets = Field(default_factory=ProviderSecrets)

    # Retry configuration
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_INITIAL_DELAY_SECONDS: float = 1.0
    RETRY_MAX_DELAY_SECONDS: float = 60.0

    # Dead Letter Queue
    DLQ_ENABLED: bool = True
    DLQ_MAX_RETRIES: int = 3

    # Dispatch settings
    DISPATCH_TIMEOUT_SECONDS: float = 10.0

    # Legacy support (will be removed in future version)
    TYPEFORM_SECRET: str = ""

    def __init__(self, **data: Any):
        super().__init__(**data)
        # If legacy TYPEFORM_SECRET is set, propagate to new location
        if self.TYPEFORM_SECRET and not self.secrets.WEBHOOK_TYPEFORM_SECRET:
            self.secrets.WEBHOOK_TYPEFORM_SECRET = self.TYPEFORM_SECRET

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> WebhookSettings:
    """Get cached settings instance."""
    return WebhookSettings()


# Global settings instance
settings = get_settings()
