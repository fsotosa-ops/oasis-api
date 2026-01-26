"""
Dead Letter Queue (DLQ) for failed webhook events.

Manages retry scheduling with exponential backoff.
Events that exceed max retries are marked as abandoned.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from common.database.client import get_admin_client

logger = logging.getLogger(__name__)


@dataclass
class DLQEntry:
    """Domain model for a DLQ entry."""

    id: UUID
    event_id: UUID
    error_message: str
    retry_count: int
    max_retries: int
    next_retry_at: datetime | None
    last_retry_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime


class DeadLetterQueue:
    """
    Dead Letter Queue for failed webhook events.

    Provides:
    - Enqueueing failed events with automatic retry scheduling
    - Fetching events ready for retry
    - Marking events as resolved or abandoned
    """

    TABLE = "webhooks.dead_letter_queue"

    def __init__(self, max_retries: int = 3):
        """
        Initialize the DLQ.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.max_retries = max_retries

    async def enqueue(
        self,
        event_id: UUID | str,
        error_message: str,
    ) -> DLQEntry:
        """
        Add a failed event to the dead letter queue.

        If the event is already in the DLQ, increments retry count.
        Uses exponential backoff for scheduling next retry.

        Args:
            event_id: The webhook event ID
            error_message: Description of the failure

        Returns:
            DLQEntry: The created or updated DLQ entry
        """
        db = await get_admin_client()
        event_id_str = str(event_id)

        # Check if entry already exists
        existing = await self.get_by_event_id(event_id)

        if existing:
            return await self._increment_retry(existing, error_message)

        # Create new entry with first retry scheduled
        data = {
            "event_id": event_id_str,
            "error_message": error_message,
            "retry_count": 0,
            "max_retries": self.max_retries,
            "status": "pending",
            # Next retry in 1 second (2^0)
            "next_retry_at": "now() + interval '1 second'",
        }

        try:
            response = await db.table(self.TABLE).insert(data).execute()

            if not response.data:
                raise ValueError("No data returned from insert")

            entry = self._row_to_entry(response.data[0])
            logger.info(
                f"Event {event_id} added to DLQ, retry scheduled"
                f"at {entry.next_retry_at}"
            )

            return entry

        except Exception as e:
            logger.error(f"Failed to enqueue event {event_id} to DLQ: {e}")
            raise

    async def _increment_retry(self, entry: DLQEntry, error_message: str) -> DLQEntry:
        """Increment retry count and reschedule or abandon."""
        db = await get_admin_client()

        new_retry_count = entry.retry_count + 1

        if new_retry_count >= entry.max_retries:
            # Max retries exceeded, abandon
            await (
                db.table(self.TABLE)
                .update(
                    {
                        "status": "abandoned",
                        "error_message": error_message,
                        "retry_count": new_retry_count,
                        "last_retry_at": "now()",
                        "next_retry_at": None,
                    }
                )
                .eq("id", str(entry.id))
                .execute()
            )
            logger.warning(
                f"Event {entry.event_id} abandoned after" f"{new_retry_count} retries"
            )
        else:
            # Schedule next retry with exponential backoff
            backoff_seconds = 2**new_retry_count
            next_retry_sql = f"now() + interval '{backoff_seconds} seconds'"
            await (
                db.table(self.TABLE)
                .update(
                    {
                        "status": "pending",
                        "error_message": error_message,
                        "retry_count": new_retry_count,
                        "last_retry_at": "now()",
                        "next_retry_at": next_retry_sql,
                    }
                )
                .eq("id", str(entry.id))
                .execute()
            )
            logger.info(
                f"Event {entry.event_id} retry "
                f"{new_retry_count} scheduled in {backoff_seconds}s"
            )

        # Return updated entry
        return await self.get_by_id(entry.id)

    async def get_by_id(self, dlq_id: UUID | str) -> DLQEntry | None:
        """Get a DLQ entry by its ID."""
        db = await get_admin_client()

        response = (
            await db.table(self.TABLE)
            .select("*")
            .eq("id", str(dlq_id))
            .single()
            .execute()
        )

        if not response.data:
            return None

        return self._row_to_entry(response.data)

    async def get_by_event_id(self, event_id: UUID | str) -> DLQEntry | None:
        """Get a DLQ entry by its event ID."""
        db = await get_admin_client()

        response = (
            await db.table(self.TABLE)
            .select("*")
            .eq("event_id", str(event_id))
            .single()
            .execute()
        )

        if not response.data:
            return None

        return self._row_to_entry(response.data)

    async def get_pending_retries(self, limit: int = 50) -> list[DLQEntry]:
        """
        Get events ready for retry (next_retry_at <= now).

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of DLQ entries ready for retry
        """
        db = await get_admin_client()

        response = (
            await db.table(self.TABLE)
            .select("*")
            .in_("status", ["pending", "retrying"])
            .lte("next_retry_at", "now()")
            .order("next_retry_at")
            .limit(limit)
            .execute()
        )

        return [self._row_to_entry(row) for row in (response.data or [])]

    async def mark_retrying(self, dlq_id: UUID | str) -> None:
        """Mark a DLQ entry as currently being retried."""
        db = await get_admin_client()

        await (
            db.table(self.TABLE)
            .update({"status": "retrying"})
            .eq("id", str(dlq_id))
            .execute()
        )

    async def mark_resolved(
        self, dlq_id: UUID | str, resolution_note: str | None = None
    ) -> None:
        """Mark a DLQ entry as successfully resolved."""
        db = await get_admin_client()

        await (
            db.table(self.TABLE)
            .update(
                {
                    "status": "resolved",
                    "resolved_at": "now()",
                    "resolution_note": resolution_note,
                }
            )
            .eq("id", str(dlq_id))
            .execute()
        )

        logger.info(f"DLQ entry {dlq_id} resolved: {resolution_note}")

    async def get_stats(self) -> dict[str, Any]:
        """Get DLQ statistics for monitoring."""
        db = await get_admin_client()

        # Count by status
        response = await db.table(self.TABLE).select("status").execute()

        stats = {
            "pending": 0,
            "retrying": 0,
            "resolved": 0,
            "abandoned": 0,
            "total": 0,
        }

        for row in response.data or []:
            status = row["status"]
            if status in stats:
                stats[status] += 1
            stats["total"] += 1

        return stats

    def _row_to_entry(self, row: dict) -> DLQEntry:
        """Convert a database row to a DLQEntry."""
        return DLQEntry(
            id=UUID(row["id"]),
            event_id=UUID(row["event_id"]),
            error_message=row["error_message"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            next_retry_at=row.get("next_retry_at"),
            last_retry_at=row.get("last_retry_at"),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# Singleton instance
_dlq: DeadLetterQueue | None = None


def get_dlq(max_retries: int = 3) -> DeadLetterQueue:
    """Get the singleton DLQ instance."""
    global _dlq
    if _dlq is None:
        _dlq = DeadLetterQueue(max_retries=max_retries)
    return _dlq
