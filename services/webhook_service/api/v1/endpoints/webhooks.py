"""
Webhook Endpoints

Dynamic webhook routing based on provider name.
All providers are auto-discovered and registered.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Query, Request

from common.errors import ErrorCodes
from common.exceptions import NotFoundError, ValidationError
from common.schemas.responses import OasisResponse
from services.webhook_service.core.registry import get_registry
from services.webhook_service.pipeline.ingestion import (
    process_webhook,
    retry_dlq_events,
)
from services.webhook_service.schemas.webhooks import (
    DLQRetryResult,
    ProviderInfo,
    ProviderStatus,
    WebhookReceived,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/{provider}",
    response_model=OasisResponse[WebhookReceived],
    summary="Recibir webhook de proveedor",
    description=(
        "Endpoint universal para recibir webhooks" "de cualquier proveedor registrado."
    ),
    responses={
        200: {"description": "Webhook recibido y encolado para procesamiento"},
        401: {"description": "Firma invalida"},
        404: {"description": "Proveedor no registrado"},
        503: {"description": "Proveedor no configurado (sin secret)"},
    },
)
async def handle_webhook(
    provider: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Endpoint universal para webhooks.

    El proveedor se resuelve desde la URL y debe:
    1. Estar registrado en el registry
    2. Tener un secret configurado

    Ejemplo: POST /api/v1/webhooks/typeform
    """
    registry = get_registry()
    provider_instance = registry.get(provider.lower())

    # Check if provider exists
    if not provider_instance:
        available = registry.list_providers()
        logger.warning(f"Proveedor desconocido solicitado: {provider}")
        raise NotFoundError(
            resource="provider",
            identifier=f"{provider} (disponibles: {', '.join(available)})",
        )

    # Check if provider is configured
    if not provider_instance.has_valid_secret():
        logger.error(f"Proveedor '{provider}' sin secret configurado")
        raise ValidationError(
            code=ErrorCodes.PROVIDER_NOT_CONFIGURED,
            message=(
                f"Proveedor '{provider}' no configurado."
                "Establece WEBHOOK_{provider.upper()}_SECRET."
            ),
        )

    # Process the webhook
    result = await process_webhook(provider_instance, request, background_tasks)

    return OasisResponse(
        success=True,
        message="Webhook recibido y encolado para procesamiento",
        data=WebhookReceived(
            trace_id=result["trace_id"],
            provider=result["provider"],
            event_type=result.get("event_type"),
        ),
    )


@router.get(
    "/providers",
    response_model=OasisResponse[ProviderStatus],
    summary="Listar proveedores",
    description="Lista todos los proveedores registrados y su estado de configuracion.",
)
async def list_providers():
    """
    Lista proveedores de webhook registrados.

    Retorna estado de configuracion de cada proveedor.
    Util para dashboards de admin y debugging.
    """
    registry = get_registry()
    status = registry.get_status()

    providers_info = {
        name: ProviderInfo(
            name=name,
            signature_header=info["signature_header"],
            secret_configured=info["secret_configured"],
        )
        for name, info in status["providers"].items()
    }

    return OasisResponse(
        success=True,
        message=(
            f"{status['configured_providers']} de"
            f"{status['total_providers']} proveedores configurados"
        ),
        data=ProviderStatus(
            total_providers=status["total_providers"],
            configured_providers=status["configured_providers"],
            providers=providers_info,
        ),
    )


@router.post(
    "/dlq/retry",
    response_model=OasisResponse[DLQRetryResult],
    summary="Reintentar eventos fallidos",
    description="Procesa manualmente eventos pendientes en la Dead Letter Queue.",
)
async def trigger_dlq_retry(
    batch_size: int = Query(default=10, ge=1, le=100, description="Eventos a procesar"),
):
    """
    Reintenta eventos de la Dead Letter Queue.

    Permite a administradores procesar manualmente
    eventos fallidos pendientes de reintento.
    """
    results = await retry_dlq_events(batch_size=batch_size)

    return OasisResponse(
        success=True,
        message=(
            f"Procesados {results['processed']}, "
            f"fallidos {results['failed']}, "
            f"omitidos {results['skipped']}"
        ),
        data=DLQRetryResult(
            processed=results["processed"],
            failed=results["failed"],
            skipped=results["skipped"],
        ),
    )
