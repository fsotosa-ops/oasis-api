"""
Webhook Event Repository

Handles persistence of webhook events to the raw storage layer.
Events are persisted BEFORE dispatch for resilience.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from common.database.client import get_admin_client

logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    """Domain model for a webhook event."""

    id: UUID
    provider: str
    external_id: str | None
    event_type: str
    raw_payload: dict[str, Any]
    normalized_payload: dict[str, Any] | None
    status: str
    user_identifier: str | None
    organization_id: UUID | None
    received_at: datetime
    processed_at: datetime | None = None
    error_message: str | None = None


class WebhookEventRepository:
    """
    Repository for webhook event persistence.

    Provides CRUD operations for the webhooks.events table.
    Uses the admin client (service role) to bypass RLS.
    """

    TABLE = "webhooks.events"

    async def create_event(
        self,
        provider: str,
        event_type: str,
        raw_payload: dict[str, Any],
        normalized_payload: dict[str, Any] | None = None,
        external_id: str | None = None,
        user_identifier: str | None = None,
        organization_id: str | None = None,
    ) -> WebhookEvent:
        """
        Create a new webhook event in the raw storage layer.

        This should be called BEFORE attempting to dispatch the event
        to ensure data is never lost.

        Args:
            provider: Provider name (e.g., 'typeform', 'stripe')
            event_type: Type of event (e.g., 'form_submission')
            raw_payload: Original payload from the provider
            normalized_payload: OASIS-normalized format
            external_id: Provider's event ID for idempotency
            user_identifier: Extracted user ID/email
            organization_id: Extracted organization context

        Returns:
            WebhookEvent: The created event

        Raises:
            Exception: If database insert fails
        """
        db = await get_admin_client()

        data = {
            "provider": provider,
            "event_type": event_type,
            "raw_payload": raw_payload,
            "normalized_payload": normalized_payload,
            "external_id": external_id,
            "user_identifier": user_identifier,
            "organization_id": organization_id,
            "status": "received",
        }

        # Remove None values to let DB defaults apply
        data = {k: v for k, v in data.items() if v is not None}

        try:
            response = await db.table(self.TABLE).insert(data).execute()

            if not response.data:
                raise ValueError("No data returned from insert")

            row = response.data[0]
            logger.info(f"Created webhook event: {row['id']} ({provider}/{event_type})")

            return self._row_to_event(row)

        except Exception as e:
            # Check for duplicate external_id (idempotency)
            if "unique_provider_external_id" in str(e):
                logger.info(f"Duplicate event ignored: {provider}/{external_id}")
                existing = await self.get_by_external_id(provider, external_id)
                if existing:
                    return existing
            logger.error(f"Failed to create webhook event: {e}")
            raise

    async def get_by_id(self, event_id: UUID | str) -> WebhookEvent | None:
        """Get an event by its ID."""
        db = await get_admin_client()

        response = (
            await db.table(self.TABLE)
            .select("*")
            .eq("id", str(event_id))
            .single()
            .execute()
        )

        if not response.data:
            return None

        return self._row_to_event(response.data)

    async def get_by_external_id(
        self, provider: str, external_id: str
    ) -> WebhookEvent | None:
        """Get an event by provider and external ID (idempotency check)."""
        db = await get_admin_client()

        response = (
            await db.table(self.TABLE)
            .select("*")
            .eq("provider", provider)
            .eq("external_id", external_id)
            .single()
            .execute()
        )

        if not response.data:
            return None

        return self._row_to_event(response.data)

    async def mark_processing(self, event_id: UUID | str) -> None:
        """Mark an event as being processed."""
        await self._update_status(event_id, "processing")

    async def mark_processed(self, event_id: UUID | str) -> None:
        """Mark an event as successfully processed."""
        db = await get_admin_client()

        await (
            db.table(self.TABLE)
            .update({"status": "processed", "processed_at": "now()"})
            .eq("id", str(event_id))
            .execute()
        )

        logger.info(f"Event {event_id} marked as processed")

    async def mark_failed(
        self, event_id: UUID | str, error_message: str | None = None
    ) -> None:
        """Mark an event as failed."""
        db = await get_admin_client()

        await (
            db.table(self.TABLE)
            .update({"status": "failed", "error_message": error_message})
            .eq("id", str(event_id))
            .execute()
        )

        logger.warning(f"Event {event_id} marked as failed: {error_message}")

    async def _update_status(self, event_id: UUID | str, status: str) -> None:
        """Update the status of an event."""
        db = await get_admin_client()

        await (
            db.table(self.TABLE)
            .update({"status": status})
            .eq("id", str(event_id))
            .execute()
        )

    async def get_failed_events(
        self, provider: str | None = None, limit: int = 100
    ) -> list[WebhookEvent]:
        """Get failed events, optionally filtered by provider."""
        db = await get_admin_client()

        query = db.table(self.TABLE).select("*").eq("status", "failed").limit(limit)

        if provider:
            query = query.eq("provider", provider)

        response = await query.order("received_at", desc=True).execute()

        return [self._row_to_event(row) for row in (response.data or [])]

    def _row_to_event(self, row: dict) -> WebhookEvent:
        """Convert a database row to a WebhookEvent."""
        return WebhookEvent(
            id=UUID(row["id"]),
            provider=row["provider"],
            external_id=row.get("external_id"),
            event_type=row["event_type"],
            raw_payload=row["raw_payload"],
            normalized_payload=row.get("normalized_payload"),
            status=row["status"],
            user_identifier=row.get("user_identifier"),
            organization_id=(
                UUID(row["organization_id"]) if row.get("organization_id") else None
            ),
            received_at=row["received_at"],
            processed_at=row.get("processed_at"),
            error_message=row.get("error_message"),
        )


# Singleton instance
_repository: WebhookEventRepository | None = None


def get_repository() -> WebhookEventRepository:
    """Get the singleton repository instance."""
    global _repository
    if _repository is None:
        _repository = WebhookEventRepository()
    return _repository
