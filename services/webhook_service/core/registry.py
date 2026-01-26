"""
Provider Registry

Auto-discovers and manages webhook providers.
Adding a new provider is as simple as creating a file in providers/
that implements BaseProvider.
"""

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import Any

from services.webhook_service.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Singleton registry that discovers and manages webhook providers.

    Usage:
        registry = get_registry()
        provider = registry.get("typeform")
        if provider:
            await provider.verify_signature(request, body)

    Adding new providers:
        1. Create a file in services/webhook_service/providers/ (e.g., stripe.py)
        2. Implement a class that extends BaseProvider
        3. The provider will be auto-discovered on startup
    """

    _instance: "ProviderRegistry | None" = None
    _providers: dict[str, BaseProvider]

    def __new__(cls) -> "ProviderRegistry":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._discovered = False
        return cls._instance

    def auto_discover(self) -> None:
        """
        Discover all BaseProvider implementations in the providers package.

        Scans services.webhook_service.providers for classes that:
        - Extend BaseProvider
        - Are not BaseProvider itself
        - Are not abstract

        Each discovered provider is instantiated and registered.
        """
        if self._discovered:
            logger.debug("Providers already discovered, skipping")
            return

        providers_package = "services.webhook_service.providers"

        try:
            # Import the package
            package = importlib.import_module(providers_package)
            package_path = Path(package.__file__).parent

            # Iterate through all modules in the package
            for _, module_name, is_pkg in pkgutil.iter_modules([str(package_path)]):
                if is_pkg or module_name == "base":
                    continue

                try:
                    module = importlib.import_module(
                        f"{providers_package}.{module_name}"
                    )

                    # Find all BaseProvider subclasses in the module
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, BaseProvider)
                            and obj is not BaseProvider
                            and not inspect.isabstract(obj)
                        ):
                            self._register_provider(obj)

                except Exception as e:
                    logger.error(f"Failed to load provider module {module_name}: {e}")

            self._discovered = True
            logger.info(
                f"Discovered {len(self._providers)} providers:"
                f"{list(self._providers.keys())}"
            )

        except Exception as e:
            logger.error(f"Failed to discover providers: {e}")

    def _register_provider(self, provider_class: type[BaseProvider]) -> None:
        """Register a provider class."""
        try:
            instance = provider_class()
            name = instance.provider_name.lower()

            if name in self._providers:
                logger.warning(
                    f"Provider '{name}' already registered, skipping duplicate"
                )
                return

            self._providers[name] = instance
            logger.info(f"Registered provider: {name} ({provider_class.__name__})")

        except Exception as e:
            logger.error(
                f"Failed to instantiate provider {provider_class.__name__}: {e}"
            )

    def register(self, provider: BaseProvider) -> None:
        """
        Manually register a provider instance.

        Args:
            provider: BaseProvider instance to register
        """
        name = provider.provider_name.lower()
        self._providers[name] = provider
        logger.info(f"Manually registered provider: {name}")

    def get(self, name: str) -> BaseProvider | None:
        """
        Get a provider by name.

        Args:
            name: Provider name (case-insensitive)

        Returns:
            BaseProvider instance or None if not found
        """
        return self._providers.get(name.lower())

    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())

    def list_all(self) -> dict[str, BaseProvider]:
        """Get all registered providers."""
        return dict(self._providers)

    def validate_secrets(self) -> dict[str, bool]:
        """
        Validate that all providers have configured secrets.

        Returns:
            Dict mapping provider name to whether secret is configured
        """
        return {
            name: provider.has_valid_secret()
            for name, provider in self._providers.items()
        }

    def get_configured_providers(self) -> list[BaseProvider]:
        """Get all providers that have configured secrets."""
        return [p for p in self._providers.values() if p.has_valid_secret()]

    def get_status(self) -> dict[str, Any]:
        """
        Get detailed status of all providers.

        Useful for health checks and monitoring.
        """
        return {
            "total_providers": len(self._providers),
            "configured_providers": len(self.get_configured_providers()),
            "providers": {
                name: {
                    "class": provider.__class__.__name__,
                    "signature_header": provider.signature_header,
                    "secret_configured": provider.has_valid_secret(),
                }
                for name, provider in self._providers.items()
            },
        }

    def clear(self) -> None:
        """Clear all registered providers. Useful for testing."""
        self._providers = {}
        self._discovered = False


# Module-level singleton access
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """
    Get the singleton registry instance.

    On first call, auto-discovers all providers.
    """
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _registry.auto_discover()
    return _registry


def reset_registry() -> None:
    """Reset the registry. Useful for testing."""
    global _registry
    if _registry:
        _registry.clear()
    _registry = None
