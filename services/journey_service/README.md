# Journey Service

**Motor de Experiencia, Progresion y Gamificacion para OASIS**

## Descripcion

Journey Service gestiona la experiencia del usuario dentro de la plataforma OASIS, incluyendo:

- **Journeys**: Rutas de aprendizaje y bienestar estructuradas por pasos
- **Enrollments**: Inscripciones de usuarios en journeys
- **Gamificacion**: Sistema de puntos, niveles y recompensas
- **Tracking**: Registro de actividades y progreso
- **Backoffice**: Administracion completa de journeys, steps, niveles y rewards

## Arquitectura

```
journey_service/
├── api/
│   └── v1/
│       ├── api.py                    # Router principal
│       └── endpoints/
│           ├── journeys.py           # Lectura de journeys (usuarios)
│           ├── enrollments.py        # Inscripciones y progreso
│           ├── tracking.py           # Registro de actividades
│           ├── gamification.py       # Stats, rewards, leaderboard
│           ├── admin_journeys.py     # CRUD journeys/steps (admin)
│           ├── admin_gamification.py # Config niveles/rewards (admin)
│           └── admin_analytics.py    # Reportes (admin)
├── core/
│   └── config.py                     # Configuracion (hereda CommonSettings)
├── crud/
│   ├── admin.py                      # Operaciones admin
│   ├── enrollments.py                # Operaciones de inscripciones
│   ├── journeys.py                   # Operaciones de journeys
│   └── gamification.py               # Operaciones de gamificacion
├── schemas/
│   ├── admin.py                      # Schemas de backoffice
│   ├── enrollments.py                # Schemas de inscripciones
│   ├── journeys.py                   # Schemas de journeys
│   ├── tracking.py                   # Schemas de actividades
│   └── gamification.py               # Schemas de stats y rewards
└── main.py                           # Aplicacion FastAPI
```

## Seguridad y Multi-tenancy

**IMPORTANTE**: Todos los endpoints respetan el aislamiento por organizacion.

### Headers Requeridos

```http
Authorization: Bearer <access_token>
X-Organization-ID: <uuid>
```

### Flujo de Autorizacion

```
Request
  ↓
JWT Validation (Bearer token)
  ↓
OrgMemberRequired() → Verifica membresia activa en X-Organization-ID
  ↓
verify_journey_belongs_to_org() → Verifica que el recurso pertenezca a la org
  ↓
Operacion permitida
```

### Roles de Acceso

| Rol | Endpoints Usuario | Endpoints Admin |
|-----|-------------------|-----------------|
| `participante` | ✅ | ❌ |
| `facilitador` | ✅ | ❌ |
| `admin` | ✅ | ✅ |
| `owner` | ✅ | ✅ |
| `platform_admin` | ✅ (todas las orgs) | ✅ (todas las orgs) |

---

## Endpoints de Usuario

Todos requieren `Authorization` + `X-Organization-ID`.

### Journeys

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/journeys/` | Listar journeys de mi organizacion |
| `GET` | `/journeys/{id}` | Detalle de journey con steps |
| `GET` | `/journeys/{id}/steps` | Steps ordenados de un journey |

### Enrollments

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `POST` | `/enrollments/` | Inscribirse en un journey |
| `GET` | `/enrollments/me` | Mis inscripciones |
| `GET` | `/enrollments/{id}` | Detalle de inscripcion con progreso |
| `GET` | `/enrollments/{id}/progress` | Progreso detallado por steps |
| `POST` | `/enrollments/{id}/complete` | Marcar journey como completado |
| `POST` | `/enrollments/{id}/drop` | Abandonar journey |
| `POST` | `/enrollments/{id}/resume` | Retomar journey abandonado |

### Gamification

| Metodo | Endpoint | Descripcion | Requiere Org |
|--------|----------|-------------|--------------|
| `GET` | `/me/stats` | Puntos, nivel, progreso general | No |
| `GET` | `/me/rewards` | Mis insignias/badges | No |
| `GET` | `/me/activity` | Historial de actividades | No |
| `GET` | `/me/points-history` | Historial de puntos | No |
| `GET` | `/me/leaderboard` | Ranking de mi organizacion | **Si** |
| `GET` | `/me/levels` | Niveles de mi organizacion | **Si** |

### Tracking

| Metodo | Endpoint | Descripcion | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/tracking/event` | Registrar actividad | 60/min |
| `POST` | `/tracking/external-event` | Evento externo (webhook_service) | Service-to-service |

---

## Endpoints de Admin (Backoffice)

Requieren rol `owner` o `admin` + `X-Organization-ID`.

### Admin - Journeys

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/admin/journeys/` | Listar journeys con estadisticas |
| `POST` | `/admin/journeys/` | Crear journey (como borrador) |
| `GET` | `/admin/journeys/{id}` | Detalle de journey con stats |
| `PUT` | `/admin/journeys/{id}` | Actualizar journey |
| `DELETE` | `/admin/journeys/{id}` | Eliminar journey (cascada) |
| `POST` | `/admin/journeys/{id}/publish` | Publicar/activar journey |
| `POST` | `/admin/journeys/{id}/archive` | Archivar/desactivar journey |
| `GET` | `/admin/journeys/{id}/stats` | Estadisticas detalladas |

### Admin - Steps

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/admin/journeys/{id}/steps` | Listar steps con stats |
| `POST` | `/admin/journeys/{id}/steps` | Crear step |
| `PUT` | `/admin/journeys/{id}/steps/{step_id}` | Actualizar step |
| `DELETE` | `/admin/journeys/{id}/steps/{step_id}` | Eliminar step |
| `POST` | `/admin/journeys/{id}/steps/reorder` | Reordenar steps |

### Admin - Levels

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/admin/levels` | Listar niveles de la org |
| `POST` | `/admin/levels` | Crear nivel |
| `PUT` | `/admin/levels/{id}` | Actualizar nivel |
| `DELETE` | `/admin/levels/{id}` | Eliminar nivel |

### Admin - Rewards

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/admin/rewards` | Listar recompensas/badges |
| `POST` | `/admin/rewards` | Crear recompensa |
| `PUT` | `/admin/rewards/{id}` | Actualizar recompensa |
| `DELETE` | `/admin/rewards/{id}` | Eliminar recompensa |

### Admin - Analytics

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/admin/enrollments` | Listar todas las inscripciones |
| `GET` | `/admin/users/{id}/progress` | Progreso de un usuario |
| `GET` | `/admin/summary` | Resumen analytics de la org |

### System

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/health` | Health check del servicio |

---

## Rate Limiting

| Endpoint | Limite | Razon |
|----------|--------|-------|
| `POST /tracking/event` | 60/min | Prevenir abuso de puntos |
| Otros endpoints | 200/min | Limite por defecto |

## Modelo de Datos

### Schema PostgreSQL (`journeys.*`)

```
journeys.journeys          # Rutas de experiencia
journeys.steps             # Pasos de cada journey
journeys.enrollments       # Inscripciones usuario-journey
journeys.step_completions  # Progreso detallado (denormalizado)
journeys.levels            # Niveles por organizacion
journeys.user_activities   # Actividades "side-quest"
journeys.rewards_catalog   # Catalogo de insignias
journeys.user_rewards      # Recompensas obtenidas
journeys.points_ledger     # Ledger transaccional de puntos
```

### RLS Policies

- Usuarios solo pueden ver/modificar sus propios datos
- Journeys visibles para miembros de la organizacion
- Ledger de puntos es solo lectura para usuarios
- Admin bypasea RLS via service_role

## Gamificacion

### Flujo de Puntos

```
1. Usuario completa actividad (POST /tracking/event)
2. Sistema calcula puntos segun reglas del step
3. Se registra en points_ledger (auditoria)
4. Trigger actualiza progress_percentage en enrollment
5. Background task verifica nivel (level_up)
```

### Tipos de Actividad

| Tipo | Puntos Base |
|------|-------------|
| `social_post` | 5 |
| `video_view` | 3 |
| `resource_view` | 2 |
| `comment` | 2 |
| `like` | 1 |

### Funciones RPC

```sql
journeys.get_user_total_points(uid)           -- Total de puntos
journeys.get_user_current_level(uid, org_id)  -- Nivel actual
journeys.calculate_enrollment_progress(id)    -- % de progreso
```

## Respuestas

Todas las respuestas usan el envelope `OasisResponse`:

```json
{
  "success": true,
  "message": "Operacion exitosa",
  "data": { ... },
  "meta": { "total": 10, "skip": 0, "limit": 50 }
}
```

Errores:

```json
{
  "success": false,
  "error": {
    "code": "journey_002",
    "message": "Ya tienes una inscripcion activa"
  }
}
```

## Ejemplos de Uso

### Usuario: Listar Journeys

```bash
curl -X GET "http://localhost:8002/api/v1/journeys/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

### Usuario: Inscribirse en Journey

```bash
curl -X POST "http://localhost:8002/api/v1/enrollments/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"journey_id": "uuid-del-journey"}'
```

### Admin: Crear Journey

```bash
curl -X POST "http://localhost:8002/api/v1/admin/journeys/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Onboarding de Bienestar",
    "slug": "onboarding-bienestar",
    "description": "Ruta de 30 dias para mejorar tu bienestar"
  }'
```

### Admin: Agregar Step

```bash
curl -X POST "http://localhost:8002/api/v1/admin/journeys/$JOURNEY_ID/steps" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Encuesta inicial",
    "type": "survey",
    "config": { "typeform_id": "abc123" },
    "gamification_rules": { "points_base": 10 }
  }'
```

### Admin: Publicar Journey

```bash
curl -X POST "http://localhost:8002/api/v1/admin/journeys/$JOURNEY_ID/publish" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

## Ejecucion

### Desarrollo

```bash
poetry run uvicorn services.journey_service.main:app --reload --port 8002
```

### Documentacion

- Swagger UI: http://localhost:8002/api/v1/docs
- ReDoc: http://localhost:8002/api/v1/redoc

## Integracion con Webhook Service

Journey Service recibe eventos externos normalizados desde el webhook_service.

### Endpoint: `/tracking/external-event`

Este endpoint es **solo para comunicacion service-to-service** con webhook_service.

```http
POST /api/v1/tracking/external-event
Authorization: Bearer {SERVICE_TO_SERVICE_TOKEN}
X-Event-Source: webhook_service
Content-Type: application/json

{
  "source": "typeform",
  "event_type": "form_submission",
  "external_id": "evt_xxx",
  "resource_id": "form_abc123",
  "occurred_at": "2026-01-25T10:30:00Z",
  "user_identifier": "user-uuid-or-email",
  "organization_id": "org-uuid",
  "metadata": {
    "enrollment_id": "enrollment-uuid",
    "journey_id": "journey-uuid",
    "step_id": "step-uuid",
    "form_id": "typeform-form-id"
  }
}
```

### Flujo de Procesamiento

```
1. webhook_service recibe webhook de Typeform
2. Valida firma HMAC-SHA256
3. Normaliza payload al formato OASIS
4. Persiste en webhooks.events (resiliencia)
5. Despacha a journey_service /external-event
6. Journey Service:
   a. Verifica idempotencia (external_event_id)
   b. Resuelve usuario por identifier
   c. Busca step asociado por form_id
   d. Registra step_completion
   e. Otorga puntos
```

### Mapeo Step <-> Typeform

Para vincular un step con un formulario Typeform, configurar `external_config`:

```json
{
  "external_config": {
    "form_id": "abc123"
  }
}
```

## Variables de Entorno

Hereda de `CommonSettings`:

```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256

# Service-to-service auth (mismo valor que en webhook_service)
SERVICE_TO_SERVICE_TOKEN=secure-random-token
```

## Tests

```bash
pytest services/journey_service/tests/
```
