"""
Base Provider Interface

Defines the contract for webhook providers using the Strategy pattern.
Each provider implements verification, parsing, and normalization.
"""

from abc import ABC, abstractmethod
from typing import Any

from fastapi import Request

from services.webhook_service.core.config import settings


class BaseProvider(ABC):
    """
    Abstract base class for webhook providers.

    Implementations must provide:
    - provider_name: Unique identifier (e.g., 'typeform', 'stripe')
    - signature_header: HTTP header containing the signature
    - verify_signature: Validate request authenticity
    - parse_payload: Extract JSON from request body
    - normalize_event: Transform to OASIS standard format
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Unique name for this provider.

        Used for:
        - URL routing (/webhooks/{provider_name})
        - Secret lookup
        - Event logging

        Returns:
            Lowercase provider name (e.g., 'typeform', 'stripe')
        """
        pass

    @property
    @abstractmethod
    def signature_header(self) -> str:
        """
        HTTP header name containing the webhook signature.

        Examples:
        - Typeform: 'Typeform-Signature'
        - Stripe: 'Stripe-Signature'
        - GitHub: 'X-Hub-Signature-256'

        Returns:
            Header name (case-insensitive in HTTP)
        """
        pass

    @abstractmethod
    async def verify_signature(self, request: Request, body: bytes) -> bool:
        """
        Validate the authenticity of the webhook request.

        This method should:
        1. Extract signature from headers
        2. Compute expected signature using provider secret
        3. Compare using timing-safe comparison

        Args:
            request: FastAPI Request object
            body: Raw request body bytes (for HMAC computation)

        Returns:
            True if signature is valid, False otherwise
        """
        pass

    @abstractmethod
    async def parse_payload(self, body: bytes) -> dict[str, Any]:
        """
        Parse the request body into a dictionary.

        Most providers use JSON, but some may use form data or XML.

        Args:
            body: Raw request body bytes

        Returns:
            Parsed payload as a dictionary
        """
        pass

    @abstractmethod
    def normalize_event(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Transform provider-specific payload to OASIS standard format.

        The normalized event should include:
        - source: Provider name
        - event_type: Type of event (e.g., 'form_submission')
        - external_id: Provider's event ID
        - resource_id: ID of the resource (form, payment, etc.)
        - occurred_at: Timestamp of the event
        - user_identifier: User ID, email, or other identifier
        - metadata: Additional context (org_id, enrollment_id, etc.)

        Args:
            raw_payload: Original payload from the provider

        Returns:
            Normalized event dictionary
        """
        pass

    # ========================================================================
    # Secret Management (Non-abstract, uses centralized config)
    # ========================================================================

    def get_secret(self) -> str | None:
        """
        Get the secret for this provider from centralized config.

        Returns:
            The provider's secret, or None if not configured
        """
        return settings.secrets.get_secret(self.provider_name)

    def has_valid_secret(self) -> bool:
        """
        Check if this provider has a configured secret.

        Returns:
            True if secret is configured and non-empty
        """
        return settings.secrets.has_secret(self.provider_name)

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def get_signature_from_request(self, request: Request) -> str | None:
        """
        Extract the signature from request headers.

        Args:
            request: FastAPI Request object

        Returns:
            Signature string or None if not present
        """
        return request.headers.get(self.signature_header)

    def __repr__(self) -> str:
        """String representation for debugging."""
        configured = "configured" if self.has_valid_secret() else "not configured"
        return (
            f"<{self.__class__.__name__}"
            f"(name={self.provider_name}, secret={configured})>"
        )
