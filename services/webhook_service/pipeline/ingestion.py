"""
Webhook Ingestion Pipeline

Handles the complete lifecycle of webhook events:
1. Signature verification
2. Payload parsing and normalization
3. Persistence to raw storage (resilience)
4. Async dispatch with retry
5. Dead letter queue for failures
"""

import asyncio
import logging
from uuid import UUID

import httpx
from fastapi import BackgroundTasks, Request

from common.errors import ErrorCodes
from common.exceptions import UnauthorizedError, ValidationError
from services.webhook_service.core.config import settings
from services.webhook_service.persistence.dlq import get_dlq
from services.webhook_service.persistence.repository import get_repository
from services.webhook_service.providers.base import BaseProvider

logger = logging.getLogger(__name__)


async def process_webhook(
    provider: BaseProvider,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Process an incoming webhook request.

    Flow:
    1. Read body once (for signature verification and parsing)
    2. Verify signature
    3. Parse and normalize payload
    4. Persist to raw storage (BEFORE dispatch for resilience)
    5. Schedule async dispatch with retry logic
    6. Return immediately (Fire & Forget pattern)

    Args:
        provider: The webhook provider instance
        request: FastAPI Request object
        background_tasks: FastAPI BackgroundTasks for async processing

    Returns:
        dict with status and trace_id

    Raises:
        HTTPException: 401 if signature is invalid, 400 if payload is malformed
    """
    # 1. Read body once (FastAPI caches it)
    body = await request.body()

    # 2. Verify signature
    if not await provider.verify_signature(request, body):
        logger.warning(f"Firma invalida para proveedor: {provider.provider_name}")
        raise UnauthorizedError(message="Firma de webhook invalida")

    # 3. Parse and normalize
    try:
        raw_payload = await provider.parse_payload(body)
    except Exception as e:
        logger.error(f"Error parseando payload de {provider.provider_name}: {e}")
        raise ValidationError(
            code=ErrorCodes.INVALID_PAYLOAD,
            message="Formato de payload invalido",
        ) from e

    normalized = provider.normalize_event(raw_payload)

    # 4. Persist to raw storage FIRST (resilience)
    repo = get_repository()
    try:
        event = await repo.create_event(
            provider=provider.provider_name,
            event_type=normalized.get("event_type", "unknown"),
            raw_payload=raw_payload,
            normalized_payload=normalized,
            external_id=normalized.get("external_id"),
            user_identifier=normalized.get("user_identifier"),
            organization_id=normalized.get("organization_id"),
        )
        event_id = event.id
        logger.info(f"Persisted event {event_id} for {provider.provider_name}")

    except Exception as e:
        # If we can't persist, log and continue with in-memory processing
        # This is a degraded mode - we lose resilience but maintain functionality
        logger.error(f"Failed to persist event, continuing with in-memory: {e}")
        event_id = normalized.get("external_id", "unknown")

    # 5. Schedule async dispatch
    background_tasks.add_task(
        _dispatch_with_retry,
        event_id=event_id,
        normalized_event=normalized,
    )

    # 6. Return immediately (Fire & Forget)
    return {
        "status": "received",
        "trace_id": str(event_id),
        "provider": provider.provider_name,
        "event_type": normalized.get("event_type"),
    }


async def _dispatch_with_retry(
    event_id: UUID | str,
    normalized_event: dict,
) -> None:
    """
    Dispatch event to journey service with exponential backoff retry.

    Args:
        event_id: The persisted event ID (for status updates)
        normalized_event: The normalized event payload

    On success:
        - Updates event status to 'processed'
    On failure after all retries:
        - Updates event status to 'failed'
        - Enqueues to Dead Letter Queue (if enabled)
    """
    repo = get_repository()
    dlq = get_dlq(max_retries=settings.DLQ_MAX_RETRIES)

    max_attempts = settings.RETRY_MAX_ATTEMPTS
    base_delay = settings.RETRY_INITIAL_DELAY_SECONDS
    max_delay = settings.RETRY_MAX_DELAY_SECONDS
    last_error = None

    # Mark as processing
    try:
        await repo.mark_processing(event_id)
    except Exception as e:
        logger.warning(f"Failed to mark event {event_id} as processing: {e}")

    for attempt in range(max_attempts):
        try:
            await _dispatch_to_journey_service(normalized_event)

            # Success! Mark as processed
            try:
                await repo.mark_processed(event_id)
            except Exception as e:
                logger.warning(f"Failed to mark event {event_id} as processed: {e}")

            logger.info(
                f"Event {event_id} dispatched successfully on attempt {attempt + 1}"
            )
            return

        except Exception as e:
            last_error = str(e)
            logger.warning(
                f"Dispatch attempt {attempt + 1}/{max_attempts}"
                f"failed for {event_id}: {e}"
            )

            if attempt < max_attempts - 1:
                # Calculate exponential backoff with jitter
                delay = min(base_delay * (2**attempt), max_delay)
                await asyncio.sleep(delay)

    # All retries exhausted
    logger.error(f"Event {event_id} failed after {max_attempts} attempts: {last_error}")

    # Mark as failed in repository
    try:
        await repo.mark_failed(event_id, last_error)
    except Exception as e:
        logger.warning(f"Failed to mark event {event_id} as failed: {e}")

    # Enqueue to DLQ if enabled
    if settings.DLQ_ENABLED:
        try:
            await dlq.enqueue(event_id, last_error)
            logger.info(f"Event {event_id} enqueued to DLQ")
        except Exception as e:
            logger.error(f"Failed to enqueue event {event_id} to DLQ: {e}")


async def _dispatch_to_journey_service(event: dict) -> None:
    """
    Send normalized event to journey service.

    Args:
        event: Normalized event payload

    Raises:
        Exception: If dispatch fails
    """
    if not settings.JOURNEY_SERVICE_URL:
        logger.warning("JOURNEY_SERVICE_URL not configured, skipping dispatch")
        return

    url = f"{settings.JOURNEY_SERVICE_URL}/api/v1/tracking/external-event"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=event,
            headers={
                "Authorization": f"Bearer {settings.SERVICE_TO_SERVICE_TOKEN}",
                "X-Event-Source": "webhook_service",
                "Content-Type": "application/json",
            },
            timeout=settings.DISPATCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()


async def retry_dlq_events(batch_size: int = 10) -> dict:
    """
    Process pending events from the Dead Letter Queue.

    This can be called by a scheduled job or admin endpoint.

    Args:
        batch_size: Maximum number of events to process

    Returns:
        dict with counts of processed, failed, and skipped events
    """
    dlq = get_dlq()
    repo = get_repository()

    pending = await dlq.get_pending_retries(limit=batch_size)
    results = {"processed": 0, "failed": 0, "skipped": 0}

    for entry in pending:
        try:
            # Mark as retrying
            await dlq.mark_retrying(entry.id)

            # Get the original event
            event = await repo.get_by_id(entry.event_id)
            if not event or not event.normalized_payload:
                logger.warning(f"Event {entry.event_id} not found for DLQ retry")
                results["skipped"] += 1
                continue

            # Attempt dispatch
            await _dispatch_to_journey_service(event.normalized_payload)

            # Success
            await repo.mark_processed(entry.event_id)
            await dlq.mark_resolved(entry.id, "Successfully retried")
            results["processed"] += 1

        except Exception as e:
            logger.error(f"DLQ retry failed for event {entry.event_id}: {e}")
            # enqueue will increment retry count and reschedule or abandon
            await dlq.enqueue(entry.event_id, str(e))
            results["failed"] += 1

    logger.info(f"DLQ retry batch complete: {results}")
    return results
