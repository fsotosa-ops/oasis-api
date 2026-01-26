"""
Stripe Webhook Provider

Handles incoming webhooks from Stripe for payment events.
Includes anti-replay protection via timestamp verification.
"""

import hashlib
import hmac
import json
import time
from datetime import UTC
from typing import Any

from fastapi import Request

from services.webhook_service.providers.base import BaseProvider


class StripeProvider(BaseProvider):
    """
    Stripe webhook provider implementation.

    Stripe webhooks have enhanced security:
    - HMAC-SHA256 signature in 'Stripe-Signature' header
    - Timestamp to prevent replay attacks (default: 5 minute tolerance)
    - Signature format: t=timestamp,v1=signature

    Reference: https://stripe.com/docs/webhooks/signatures
    """

    # Maximum age of a webhook event (in seconds) to prevent replay attacks
    TIMESTAMP_TOLERANCE = 300  # 5 minutes

    @property
    def provider_name(self) -> str:
        return "stripe"

    @property
    def signature_header(self) -> str:
        return "Stripe-Signature"

    async def verify_signature(self, request: Request, body: bytes) -> bool:
        """
        Validate Stripe's webhook signature with replay protection.

        Stripe signature format: t={timestamp},v1={signature}
        The signature is computed over: {timestamp}.{payload}
        """
        sig_header = self.get_signature_from_request(request)
        secret = self.get_secret()

        # Fail securely if signature or secret is missing
        if not sig_header or not secret:
            return False

        # Parse signature header
        elements = self._parse_signature_header(sig_header)
        timestamp = elements.get("t")
        signatures = elements.get("v1", [])

        if not timestamp or not signatures:
            return False

        # Anti-replay: verify timestamp is recent
        try:
            timestamp_int = int(timestamp)
            current_time = int(time.time())

            if abs(current_time - timestamp_int) > self.TIMESTAMP_TOLERANCE:
                # Timestamp too old or in the future
                return False
        except ValueError:
            return False

        # Compute expected signature
        signed_payload = f"{timestamp}.{body.decode('utf-8')}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            msg=signed_payload.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Compare with any of the provided signatures (Stripe may send multiple)
        return any(hmac.compare_digest(expected_sig, sig) for sig in signatures)

    def _parse_signature_header(self, header: str) -> dict[str, Any]:
        """
        Parse Stripe's signature header.

        Format: t=timestamp,v1=sig1,v1=sig2,...
        Returns: {"t": "timestamp", "v1": ["sig1", "sig2"]}
        """
        result: dict[str, Any] = {"v1": []}

        for item in header.split(","):
            if "=" not in item:
                continue

            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key == "t":
                result["t"] = value
            elif key == "v1":
                result["v1"].append(value)

        return result

    async def parse_payload(self, body: bytes) -> dict[str, Any]:
        """Parse JSON payload from Stripe."""
        return json.loads(body.decode("utf-8"))

    def normalize_event(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Transform Stripe payload to OASIS standard format.

        Stripe events have structure:
        {
            "id": "evt_xxx",
            "type": "payment_intent.succeeded",
            "data": {
                "object": { ...payment/subscription details... }
            },
            "created": 1234567890
        }
        """
        event_type = raw_payload.get("type", "unknown")
        data_object = raw_payload.get("data", {}).get("object", {})

        # Extract user context from metadata (if present)
        metadata = data_object.get("metadata", {})

        # Get customer email for user identification
        customer_email = data_object.get("receipt_email") or data_object.get(
            "customer_email"
        )

        return {
            # Standard event fields
            "source": self.provider_name,
            "event_type": event_type,
            "external_id": raw_payload.get("id"),
            "resource_id": data_object.get("id"),  # payment_intent_id, etc.
            "occurred_at": self._timestamp_to_iso(raw_payload.get("created")),
            # User identification (from metadata or customer email)
            "user_identifier": metadata.get("user_id") or customer_email,
            "organization_id": metadata.get("org_id")
            or metadata.get("organization_id"),
            # Additional context
            "metadata": {
                "customer_id": data_object.get("customer"),
                "amount": data_object.get("amount"),
                "currency": data_object.get("currency"),
                "status": data_object.get("status"),
                "enrollment_id": metadata.get("enrollment_id"),
                "journey_id": metadata.get("journey_id"),
                "step_id": metadata.get("step_id"),
                # Stripe-specific identifiers
                "payment_intent_id": (
                    data_object.get("id")
                    if event_type.startswith("payment_intent")
                    else None
                ),
                "subscription_id": (
                    data_object.get("id")
                    if event_type.startswith("customer.subscription")
                    else None
                ),
                "invoice_id": (
                    data_object.get("id") if event_type.startswith("invoice") else None
                ),
            },
        }

    def _timestamp_to_iso(self, timestamp: int | None) -> str | None:
        """Convert Unix timestamp to ISO format."""
        if timestamp is None:
            return None

        from datetime import datetime

        return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
