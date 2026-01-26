# Webhook Service

**Universal Event Gateway para Integraciones Externas de OASIS**

## Descripcion

Webhook Service es el punto de entrada centralizado para todos los webhooks de proveedores externos. Gestiona:

- **Recepcion de Webhooks**: Typeform, Stripe, Zoom y otros proveedores
- **Verificacion de Firmas**: HMAC-SHA256 con timing-attack resistance
- **Normalizacion**: Transforma payloads a formato OASIS estandar
- **Resiliencia**: Persistencia antes de procesamiento + Dead Letter Queue
- **Despacho**: Envia eventos normalizados a journey_service

## Arquitectura

```
webhook_service/
├── api/v1/
│   ├── api.py                    # Router principal
│   └── endpoints/
│       └── webhooks.py           # Endpoints dinamicos
├── core/
│   ├── config.py                 # Configuracion (hereda CommonSettings)
│   └── registry.py               # Auto-descubrimiento de proveedores
├── providers/
│   ├── base.py                   # Interfaz BaseProvider
│   ├── typeform.py               # Proveedor Typeform
│   └── stripe.py                 # Proveedor Stripe
├── pipeline/
│   └── ingestion.py              # Pipeline de procesamiento
├── persistence/
│   ├── repository.py             # CRUD de eventos
│   └── dlq.py                    # Dead Letter Queue
├── schemas/
│   └── webhooks.py               # Schemas de respuesta
└── main.py                       # Aplicacion FastAPI
```

## Flujo de Procesamiento

```
                    ┌─────────────────┐
                    │   Proveedor     │
                    │   (Typeform)    │
                    └────────┬────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  POST /webhooks/typeform │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  1. Verificar Firma      │
              │     (HMAC-SHA256)        │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  2. Parsear & Normalizar │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  3. Persistir en Raw     │ ← Resiliencia
              │     (webhooks.events)    │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  4. Responder 200 OK     │ ← Fire & Forget
              └──────────────┬───────────┘
                             │
                             ▼ (Background)
              ┌──────────────────────────┐
              │  5. Despachar a          │
              │     journey_service      │
              └──────────────┬───────────┘
                             │
              ┌──────────────┴───────────┐
              │                          │
              ▼                          ▼
        ┌──────────┐              ┌──────────────┐
        │ Success  │              │ Retry (3x)   │
        │ → Done   │              │ → Backoff    │
        └──────────┘              └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │ DLQ          │
                                  │ (Manual)     │
                                  └──────────────┘
```

---

## Endpoints

### Webhooks

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `POST` | `/webhooks/{provider}` | Recibir webhook de cualquier proveedor |
| `GET` | `/webhooks/providers` | Listar proveedores y estado de configuracion |
| `POST` | `/webhooks/dlq/retry` | Reintentar eventos fallidos manualmente |

### System

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/health` | Health check del servicio |

---

## Proveedores Soportados

### Typeform

- **Header de Firma**: `Typeform-Signature`
- **Algoritmo**: HMAC-SHA256 (Base64)
- **Formato**: `sha256={hash}`
- **Secret**: `WEBHOOK_TYPEFORM_SECRET`

```bash
# Ejemplo de uso
curl -X POST "https://api.oasis.com/api/v1/webhooks/typeform" \
  -H "Typeform-Signature: sha256=abc123..." \
  -H "Content-Type: application/json" \
  -d '{"event_id": "...", "form_response": {...}}'
```

### Stripe

- **Header de Firma**: `Stripe-Signature`
- **Algoritmo**: HMAC-SHA256 con timestamp anti-replay
- **Formato**: `t={timestamp},v1={signature}`
- **Secret**: `WEBHOOK_STRIPE_SECRET`
- **Anti-replay**: Tolerancia de 5 minutos

```bash
# Ejemplo de uso
curl -X POST "https://api.oasis.com/api/v1/webhooks/stripe" \
  -H "Stripe-Signature: t=1234567890,v1=abc123..." \
  -H "Content-Type: application/json" \
  -d '{"id": "evt_xxx", "type": "payment_intent.succeeded", ...}'
```

---

## Agregar Nuevos Proveedores

Agregar un proveedor es simple gracias al auto-descubrimiento:

### 1. Crear archivo en `providers/`

```python
# providers/zoom.py
from services.webhook_service.providers.base import BaseProvider

class ZoomProvider(BaseProvider):
    @property
    def provider_name(self) -> str:
        return "zoom"

    @property
    def signature_header(self) -> str:
        return "X-Zm-Signature"

    async def verify_signature(self, request, body) -> bool:
        # Implementar verificacion de Zoom
        ...

    async def parse_payload(self, body) -> dict:
        return json.loads(body)

    def normalize_event(self, raw_payload) -> dict:
        return {
            "source": self.provider_name,
            "event_type": raw_payload.get("event"),
            "external_id": raw_payload.get("event_id"),
            ...
        }
```

### 2. Configurar secret

```env
WEBHOOK_ZOOM_SECRET=your_zoom_secret
```

### 3. Listo!

El proveedor estara disponible automaticamente en:
```
POST /api/v1/webhooks/zoom
```

---

## Formato de Evento Normalizado

Todos los proveedores normalizan al siguiente formato:

```json
{
  "source": "typeform",
  "event_type": "form_submission",
  "external_id": "evt_abc123",
  "resource_id": "form_xyz789",
  "occurred_at": "2026-01-25T10:30:00Z",
  "user_identifier": "user-uuid-or-email",
  "organization_id": "org-uuid",
  "metadata": {
    "enrollment_id": "enrollment-uuid",
    "journey_id": "journey-uuid",
    "step_id": "step-uuid",
    "form_id": "typeform-form-id",
    "response_token": "abc123"
  }
}
```

### Campos Clave

| Campo | Descripcion |
|-------|-------------|
| `source` | Nombre del proveedor |
| `event_type` | Tipo de evento (form_submission, payment_intent.succeeded) |
| `external_id` | ID del evento en el proveedor (idempotencia) |
| `resource_id` | ID del recurso (form, payment_intent, etc.) |
| `user_identifier` | ID o email del usuario para resolver en OASIS |
| `organization_id` | Contexto de organizacion |
| `metadata` | Datos adicionales para procesamiento de negocio |

---

## Resiliencia

### Persistencia Antes de Dispatch

Todos los eventos se guardan en `webhooks.events` **antes** de intentar el despacho:

```sql
webhooks.events
├── id (UUID)
├── provider (TEXT)
├── external_id (TEXT)        -- Idempotencia
├── event_type (TEXT)
├── raw_payload (JSONB)       -- Payload original
├── normalized_payload (JSONB)
├── status (TEXT)             -- received, processing, processed, failed
├── user_identifier (TEXT)
├── organization_id (UUID)
├── received_at (TIMESTAMPTZ)
└── processed_at (TIMESTAMPTZ)
```

### Retry con Backoff Exponencial

Si el despacho a journey_service falla:

1. **Intento 1**: Inmediato
2. **Intento 2**: +1 segundo
3. **Intento 3**: +2 segundos

### Dead Letter Queue

Eventos que fallan todos los reintentos van a DLQ:

```sql
webhooks.dead_letter_queue
├── id (UUID)
├── event_id (UUID)           -- Referencia a webhooks.events
├── error_message (TEXT)
├── retry_count (INT)
├── next_retry_at (TIMESTAMPTZ)
└── status (TEXT)             -- pending, retrying, resolved, abandoned
```

Reintentar manualmente:
```bash
curl -X POST "http://localhost:8004/api/v1/webhooks/dlq/retry?batch_size=10"
```

---

## Respuestas

Todas las respuestas usan el envelope `OasisResponse`:

### Exito

```json
{
  "success": true,
  "message": "Webhook recibido y encolado para procesamiento",
  "data": {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "provider": "typeform",
    "event_type": "form_submission"
  }
}
```

### Error - Firma Invalida

```json
{
  "success": false,
  "error": {
    "code": "auth_001",
    "message": "Firma de webhook invalida"
  }
}
```

### Error - Proveedor No Encontrado

```json
{
  "success": false,
  "error": {
    "code": "provider_not_found",
    "message": "provider con id zoom (disponibles: typeform, stripe) no encontrado"
  }
}
```

### Error - Proveedor No Configurado

```json
{
  "success": false,
  "error": {
    "code": "webhook_003",
    "message": "Proveedor 'zoom' no configurado. Establece WEBHOOK_ZOOM_SECRET."
  }
}
```

---

## Variables de Entorno

### Requeridas

```env
# Supabase (heredadas de CommonSettings)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256

# Service-to-service (mismo valor que en journey_service)
SERVICE_TO_SERVICE_TOKEN=secure-random-token
JOURNEY_SERVICE_URL=http://localhost:8002
```

### Secrets de Proveedores

```env
WEBHOOK_TYPEFORM_SECRET=your_typeform_webhook_secret
WEBHOOK_STRIPE_SECRET=whsec_xxx
WEBHOOK_ZOOM_SECRET=your_zoom_secret
```

### Configuracion Opcional

```env
# Retry
RETRY_MAX_ATTEMPTS=3
RETRY_INITIAL_DELAY_SECONDS=1.0
RETRY_MAX_DELAY_SECONDS=60.0

# Dead Letter Queue
DLQ_ENABLED=true
DLQ_MAX_RETRIES=3

# Dispatch
DISPATCH_TIMEOUT_SECONDS=10.0
```

---

## Ejecucion

### Desarrollo

```bash
poetry run uvicorn services.webhook_service.main:app --reload --port 8004
```

### Logs de Startup

```
INFO:     Iniciando Webhook Service...
INFO:     Descubiertos 2 proveedor(es)
INFO:       [OK] typeform - configurado y listo
WARNING:    [!!] stripe - NO CONFIGURADO (establecer WEBHOOK_STRIPE_SECRET)
INFO:     Journey Service URL: http://localhost:8002
INFO:     Dead Letter Queue: HABILITADO (max reintentos: 3)
```

### Documentacion

- Swagger UI: http://localhost:8004/api/v1/docs
- ReDoc: http://localhost:8004/api/v1/redoc

---

## Testing

### Test Manual - Typeform

```bash
# Generar firma
SECRET="your_typeform_secret"
PAYLOAD='{"event_id":"test123","form_response":{"form_id":"abc","submitted_at":"2026-01-25T10:00:00Z","hidden":{"user_id":"user-uuid"}}}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" -binary | base64)

curl -X POST "http://localhost:8004/api/v1/webhooks/typeform" \
  -H "Typeform-Signature: sha256=$SIGNATURE" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
```

### Tests Automatizados

```bash
pytest services/webhook_service/tests/
```

---

## Monitoreo

### Health Check

```bash
curl http://localhost:8004/health
```

```json
{
  "success": true,
  "message": "Webhook Service operativo",
  "data": {
    "status": "ok",
    "service": "webhook_service",
    "providers": {
      "total": 2,
      "configured": 1
    },
    "dlq_enabled": true
  }
}
```

### Estado de Proveedores

```bash
curl http://localhost:8004/api/v1/webhooks/providers
```

```json
{
  "success": true,
  "message": "1 de 2 proveedores configurados",
  "data": {
    "total_providers": 2,
    "configured_providers": 1,
    "providers": {
      "typeform": {
        "name": "typeform",
        "signature_header": "Typeform-Signature",
        "secret_configured": true
      },
      "stripe": {
        "name": "stripe",
        "signature_header": "Stripe-Signature",
        "secret_configured": false
      }
    }
  }
}
```

---

## Seguridad

### Verificacion de Firmas

- Cada proveedor implementa su propio algoritmo de verificacion
- Se usa `hmac.compare_digest()` para prevenir timing attacks
- Secretos aislados por proveedor

### Anti-Replay (Stripe)

- Stripe incluye timestamp en la firma
- Se rechaza si el timestamp tiene mas de 5 minutos

### Aislamiento

- webhook_service **no accede a datos de usuarios**
- Solo persiste eventos y los despacha a journey_service
- Autenticacion service-to-service con token dedicado

---

## Diagrama de Base de Datos

```
┌─────────────────────────────────────────────────────┐
│                    webhooks schema                   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────────────┐      ┌─────────────────────┐  │
│  │    events       │      │  dead_letter_queue  │  │
│  ├─────────────────┤      ├─────────────────────┤  │
│  │ id              │──┐   │ id                  │  │
│  │ provider        │  │   │ event_id ───────────┼──┘
│  │ external_id     │  │   │ error_message       │
│  │ event_type      │  │   │ retry_count         │
│  │ raw_payload     │  │   │ next_retry_at       │
│  │ normalized_     │  │   │ status              │
│  │   payload       │  │   │ created_at          │
│  │ status          │  │   └─────────────────────┘
│  │ user_identifier │  │
│  │ organization_id │  │
│  │ received_at     │  │
│  │ processed_at    │  │
│  └─────────────────┘  │
│                       │
└───────────────────────┴─────────────────────────────┘
```
