#!/bin/bash

# Define la ruta base del servicio
BASE_DIR="services/webhook_service"

echo "🚀 Iniciando creación del Webhook Service en: $BASE_DIR"

# 1. Crear estructura de directorios
echo "📂 Creando carpetas..."
mkdir -p "$BASE_DIR/api/v1/endpoints"
mkdir -p "$BASE_DIR/core"
mkdir -p "$BASE_DIR/pipeline"
mkdir -p "$BASE_DIR/providers"
mkdir -p "$BASE_DIR/schemas"

# 2. Crear archivos __init__.py para que Python reconozca los paquetes
echo "🐍 Creando __init__.py..."
touch "$BASE_DIR/__init__.py"
touch "$BASE_DIR/api/__init__.py"
touch "$BASE_DIR/api/v1/__init__.py"
touch "$BASE_DIR/api/v1/endpoints/__init__.py"
touch "$BASE_DIR/core/__init__.py"
touch "$BASE_DIR/pipeline/__init__.py"
touch "$BASE_DIR/providers/__init__.py"
touch "$BASE_DIR/schemas/__init__.py"

# 3. Escribir el código de los archivos

# --- CORE / CONFIG ---
echo "📝 Escribiendo core/config.py..."
cat <<EOF > "$BASE_DIR/core/config.py"
from common.config import CommonSettings

class WebhookSettings(CommonSettings):
    TYPEFORM_SECRET: str
    JOURNEY_SERVICE_URL: str = "http://localhost:8002" # Ajustar puerto según corresponda
    SERVICE_TO_SERVICE_TOKEN: str # Token para autenticación interna

    class Config:
        env_file = ".env"

settings = WebhookSettings()
EOF

# --- PROVIDERS / BASE (Interface) ---
echo "📝 Escribiendo providers/base.py..."
cat <<EOF > "$BASE_DIR/providers/base.py"
from abc import ABC, abstractmethod
from typing import Any, Dict
from fastapi import Request

class BaseProvider(ABC):
    """
    Clase abstracta que define el contrato para cualquier proveedor de webhooks.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nombre único del proveedor (ej: 'typeform', 'stripe')."""
        pass

    @abstractmethod
    async def verify_signature(self, request: Request) -> bool:
        """
        Valida la autenticidad de la petición (HMAC, Firmas, IPs).
        """
        pass

    @abstractmethod
    async def parse_payload(self, request: Request) -> Dict[str, Any]:
        """
        Extrae y devuelve el JSON del cuerpo de la petición de forma segura.
        """
        pass

    @abstractmethod
    def normalize_event(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Traduce el evento externo a un formato estándar de OASIS.
        Debe extraer la trazabilidad (user_id, enrollment_id, etc.).
        """
        pass
EOF

# --- PROVIDERS / TYPEFORM ---
echo "📝 Escribiendo providers/typeform.py..."
cat <<EOF > "$BASE_DIR/providers/typeform.py"
import hmac
import hashlib
import base64
from typing import Any, Dict
from fastapi import Request
from services.webhook_service.providers.base import BaseProvider
from services.webhook_service.core.config import settings

class TypeformProvider(BaseProvider):
    provider_name = "typeform"

    async def verify_signature(self, request: Request) -> bool:
        signature = request.headers.get("Typeform-Signature")
        # Si no hay secreto configurado, fallamos seguro
        if not signature or not settings.TYPEFORM_SECRET:
            return False

        # Leemos el body como bytes para el hash
        body = await request.body()

        # Validación HMAC-SHA256 estándar de Typeform
        digest = hmac.new(
            settings.TYPEFORM_SECRET.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256
        ).digest()

        computed_hash = base64.b64encode(digest).decode()
        expected = f"sha256={computed_hash}"

        return hmac.compare_digest(signature, expected)

    async def parse_payload(self, request: Request) -> Dict[str, Any]:
        return await request.json()

    def normalize_event(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrae el contexto de trazabilidad de los 'hidden' fields de Typeform.
        """
        form_response = raw_payload.get("form_response", {})
        hidden = form_response.get("hidden", {})

        return {
            "source": self.provider_name,
            "event_type": "form_submission",
            "external_id": raw_payload.get("event_id"),
            "resource_id": form_response.get("form_id"),  # ID del Formulario
            "occurred_at": form_response.get("submitted_at"),

            # --- Trazabilidad Clave ---
            "user_identifier": hidden.get("user_id"),
            "metadata": {
                "organization_id": hidden.get("org_id"),
                "enrollment_id": hidden.get("enrollment_id"),
                "journey_id": hidden.get("journey_id"),
                "response_token": form_response.get("token")
            },
            "raw_payload": raw_payload
        }
EOF

# --- PIPELINE / INGESTION ---
echo "📝 Escribiendo pipeline/ingestion.py..."
cat <<EOF > "$BASE_DIR/pipeline/ingestion.py"
import httpx
from fastapi import Request, BackgroundTasks, HTTPException
from services.webhook_service.providers.base import BaseProvider
from services.webhook_service.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def process_webhook(
    provider: BaseProvider,
    request: Request,
    background_tasks: BackgroundTasks
):
    # 1. Seguridad
    if not await provider.verify_signature(request):
        logger.warning(f"Firma inválida para {provider.provider_name}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parsing y Normalización
    raw_payload = await provider.parse_payload(request)
    normalized_event = provider.normalize_event(raw_payload)

    # 3. Dispatch Asíncrono (Fire & Forget)
    # Respondemos 200 OK rápido al proveedor y procesamos en background
    background_tasks.add_task(_dispatch_to_journey_service, normalized_event)

    return {"status": "received", "trace_id": normalized_event["external_id"]}

async def _dispatch_to_journey_service(event: dict):
    """
    Envía el evento normalizado al Journey Service para procesamiento de negocio.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.JOURNEY_SERVICE_URL}/api/v1/tracking/external-event",
                json=event,
                headers={
                    "Authorization": f"Bearer {settings.SERVICE_TO_SERVICE_TOKEN}",
                    "X-Event-Source": "webhook_service"
                },
                timeout=10.0
            )
            response.raise_for_status()
            logger.info(f"Evento enviado a Journey Service: {event['external_id']}")

        except Exception as e:
            logger.error(f"Error contactando Journey Service: {e}")
            # TODO: Implementar persistencia de fallos (Dead Letter Queue) si es crítico
EOF

# --- API / ENDPOINTS / WEBHOOKS ---
echo "📝 Escribiendo api/v1/endpoints/webhooks.py..."
cat <<EOF > "$BASE_DIR/api/v1/endpoints/webhooks.py"
from fastapi import APIRouter, Request, BackgroundTasks
from services.webhook_service.providers.typeform import TypeformProvider
from services.webhook_service.pipeline.ingestion import process_webhook

router = APIRouter()

# Instancias de proveedores (Singletons)
typeform_provider = TypeformProvider()

@router.post("/typeform")
async def handle_typeform_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recibe webhooks de Typeform, valida firma y normaliza datos.
    """
    return await process_webhook(typeform_provider, request, background_tasks)
EOF

# --- API / MAIN ROUTER ---
echo "📝 Escribiendo api/v1/api.py..."
cat <<EOF > "$BASE_DIR/api/v1/api.py"
from fastapi import APIRouter
from services.webhook_service.api.v1.endpoints import webhooks

api_router = APIRouter()
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
EOF

# --- MAIN APP ---
echo "📝 Escribiendo main.py..."
cat <<EOF > "$BASE_DIR/main.py"
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.webhook_service.api.v1.api import api_router
from services.webhook_service.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Webhook Service...")
    yield
    logger.info("Stopping Webhook Service...")

app = FastAPI(
    title="OASIS Webhook Service",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
    description="Universal Event Gateway para integraciones externas (Typeform, Stripe, etc.)"
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "service": "webhook_service"}
EOF

echo "✅ ¡Webhook Service creado exitosamente!"
echo "👉 Ejecuta 'chmod +x setup_webhook_service.sh' y luego './setup_webhook_service.sh'"
