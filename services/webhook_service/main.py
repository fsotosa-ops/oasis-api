"""
OASIS Webhook Service

Universal Event Gateway para integraciones externas.
Recibe webhooks de Typeform, Stripe y otros proveedores,
valida firmas, normaliza payloads y despacha a journey_service.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.exceptions import OasisException, oasis_exception_handler
from common.schemas.responses import OasisResponse
from services.webhook_service.api.v1.api import api_router
from services.webhook_service.core.config import settings
from services.webhook_service.core.registry import get_registry
from services.webhook_service.schemas.webhooks import HealthStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    On startup:
    - Descubre y registra todos los proveedores de webhook
    - Valida configuracion de proveedores
    - Log de estado de inicio

    On shutdown:
    - Limpia recursos
    """
    # Startup
    logger.info("Iniciando Webhook Service...")

    # Initialize provider registry
    registry = get_registry()
    status = registry.get_status()

    logger.info(f"Descubiertos {status['total_providers']} proveedor(es)")

    # Log configuration status for each provider
    configured_count = 0
    for name, info in status["providers"].items():
        if info["secret_configured"]:
            logger.info(f"  [OK] {name} - configurado y listo")
            configured_count += 1
        else:
            logger.warning(
                f"  [!!] {name} - NO CONFIGURADO"
                f"(establecer WEBHOOK_{name.upper()}_SECRET)"
            )

    if configured_count == 0:
        logger.warning(
            "Ningun proveedor configurado!"
            "Webhooks retornaran 503 hasta que se configuren secrets."
        )

    # Validate service-to-service token
    if not settings.SERVICE_TO_SERVICE_TOKEN:
        logger.warning(
            "SERVICE_TO_SERVICE_TOKEN no configurado -"
            "despacho a journey_service puede fallar"
        )

    # Log journey service URL
    logger.info(f"Journey Service URL: {settings.JOURNEY_SERVICE_URL}")

    # Log DLQ status
    if settings.DLQ_ENABLED:
        logger.info(
            f"Dead Letter Queue: HABILITADO"
            f"(max reintentos: {settings.DLQ_MAX_RETRIES})"
        )
    else:
        logger.info("Dead Letter Queue: DESHABILITADO")

    yield

    # Shutdown
    logger.info("Deteniendo Webhook Service...")


API_DESCRIPTION = """
Universal Event Gateway para
integraciones externas.

## Descripcion
Este servicio recibe webhooks de proveedores
externos (Typeform, Stripe, etc.),
valida firmas, normaliza payloads y despacha
eventos al journey service.

## Caracteristicas
- **Auto-descubrimiento**: Nuevos proveedores se registran
   automaticamente
- **Verificacion de Firma**: Cada proveedor
  tiene su propia verificacion segura
- **Almacenamiento Raw**: Todos los eventos
  se persisten antes de procesar (resiliencia)
- **Retry con Backoff**: Despachos fallidos
  se reintentan con backoff exponencial
- **Dead Letter Queue**: Fallos persistentes
  se encolan para retry manual

## Agregar Nuevos Proveedores
1. Crear archivo en `providers/`
   que implemente `BaseProvider`
2. Establecer variable de entorno
   `WEBHOOK_{PROVIDER}_SECRET`
3. El proveedor estara automaticamente
   disponible en `/api/v1/webhooks/{provider}`

## Endpoints
- `POST /api/v1/webhooks/{provider}` - Recibir webhook
   de cualquier proveedor
- `GET /api/v1/webhooks/providers` - Listar proveedores
   registrados y estado
- `POST /api/v1/webhooks/dlq/retry` - Reintentar eventos
   fallidos manualmente
"""

app = FastAPI(
    title="OASIS Webhook Service",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# Register exception handler for consistent error responses
app.add_exception_handler(OasisException, oasis_exception_handler)

app.include_router(api_router, prefix="/api/v1")


@app.get(
    "/health",
    response_model=OasisResponse[HealthStatus],
    tags=["System"],
    summary="Health check",
)
async def health_check():
    """
    Health check del servicio.

    Retorna estado del servicio y resumen de configuracion de proveedores.
    """
    registry = get_registry()
    status = registry.get_status()

    return OasisResponse(
        success=True,
        message="Webhook Service operativo",
        data=HealthStatus(
            status="ok",
            service="webhook_service",
            providers={
                "total": status["total_providers"],
                "configured": status["configured_providers"],
            },
            dlq_enabled=settings.DLQ_ENABLED,
        ),
    )
