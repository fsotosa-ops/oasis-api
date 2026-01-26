"""
Typeform Webhook Provider

Handles incoming webhooks from Typeform form submissions.
Validates HMAC-SHA256 signatures and extracts traceability from hidden fields.
"""

import base64
import hashlib
import hmac
import json
from typing import Any

from fastapi import Request

from services.webhook_service.providers.base import BaseProvider


class TypeformProvider(BaseProvider):
    """
    Typeform webhook provider implementation.

    Typeform sends webhooks with:
    - HMAC-SHA256 signature in 'Typeform-Signature' header
    - JSON payload with form_response containing answers and hidden fields
    """

    @property
    def provider_name(self) -> str:
        return "typeform"

    @property
    def signature_header(self) -> str:
        return "Typeform-Signature"

    async def verify_signature(self, request: Request, body: bytes) -> bool:
        """
        Validate Typeform's HMAC-SHA256 signature.

        Typeform sends signature in format: sha256={base64_encoded_hash}
        """
        signature = self.get_signature_from_request(request)
        secret = self.get_secret()

        # Fail securely if signature or secret is missing
        if not signature or not secret:
            return False

        # Compute expected signature
        digest = hmac.new(
            secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).digest()

        computed_hash = base64.b64encode(digest).decode()
        expected = f"sha256={computed_hash}"

        # Timing-safe comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected)

    async def parse_payload(self, body: bytes) -> dict[str, Any]:
        """Parse JSON payload from Typeform."""
        return json.loads(body.decode("utf-8"))

    def normalize_event(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Transform Typeform payload to OASIS standard format.

        Extracts traceability from hidden fields (user_id, org_id, etc.).
        These are configured in the Typeform form as hidden fields.
        """
        form_response = raw_payload.get("form_response", {})
        hidden = form_response.get("hidden", {})

        # Extract organization_id for persistence layer
        org_id = hidden.get("org_id") or hidden.get("organization_id")

        return {
            # Standard event fields
            "source": self.provider_name,
            "event_type": "form_submission",
            "external_id": raw_payload.get("event_id"),
            "resource_id": form_response.get("form_id"),
            "occurred_at": form_response.get("submitted_at"),
            # Traceability (extracted from hidden fields)
            "user_identifier": hidden.get("user_id") or hidden.get("email"),
            "organization_id": org_id,
            # Additional metadata for business logic
            "metadata": {
                "enrollment_id": hidden.get("enrollment_id"),
                "journey_id": hidden.get("journey_id"),
                "step_id": hidden.get("step_id"),
                "response_token": form_response.get("token"),
                "form_id": form_response.get("form_id"),
            },
        }
