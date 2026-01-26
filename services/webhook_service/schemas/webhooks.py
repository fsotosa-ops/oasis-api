"""
Webhook Service Schemas

Pydantic models for webhook responses and payloads.
"""

from pydantic import BaseModel, Field


class WebhookReceived(BaseModel):
    """Response when a webhook is successfully received."""

    trace_id: str = Field(..., description="ID para rastrear el evento")
    provider: str = Field(..., description="Proveedor del webhook")
    event_type: str | None = Field(None, description="Tipo de evento normalizado")


class ProviderInfo(BaseModel):
    """Information about a registered provider."""

    name: str = Field(..., description="Nombre del proveedor")
    signature_header: str = Field(..., description="Header de firma")
    secret_configured: bool = Field(..., description="Si el secret esta configurado")


class ProviderStatus(BaseModel):
    """Status of all registered providers."""

    total_providers: int = Field(..., description="Total de proveedores registrados")
    configured_providers: int = Field(
        ..., description="Proveedores con secret configurado"
    )
    providers: dict[str, ProviderInfo] = Field(..., description="Detalle por proveedor")


class DLQRetryResult(BaseModel):
    """Result of DLQ retry operation."""

    processed: int = Field(..., description="Eventos procesados exitosamente")
    failed: int = Field(..., description="Eventos que fallaron el retry")
    skipped: int = Field(..., description="Eventos omitidos (no encontrados)")


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Estado del servicio")
    service: str = Field(..., description="Nombre del servicio")
    providers: dict[str, int] = Field(..., description="Estado de proveedores")
    dlq_enabled: bool = Field(..., description="Si DLQ esta habilitado")
