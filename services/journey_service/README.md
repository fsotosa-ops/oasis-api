# Journey Service

**Motor de Experiencia, Progresión y Gamificación para OASIS**

## Descripcion

Journey Service gestiona la experiencia del usuario dentro de la plataforma OASIS, incluyendo:

- **Journeys**: Rutas de aprendizaje y bienestar estructuradas por pasos
- **Enrollments**: Inscripciones de usuarios en journeys
- **Gamificacion**: Sistema de puntos, niveles y recompensas
- **Tracking**: Registro de actividades y progreso

## Arquitectura

```
journey_service/
├── api/
│   └── v1/
│       ├── api.py              # Router principal
│       └── endpoints/
│           ├── enrollments.py  # Inscripciones en journeys
│           └── tracking.py     # Registro de actividades
├── core/
│   └── config.py               # Configuracion (hereda de CommonSettings)
├── crud/
│   └── enrollments.py          # Operaciones de base de datos
├── logic/
│   └── gamification.py         # Calculo de puntos y niveles
├── schemas/
│   ├── enrollments.py          # Schemas de inscripciones
│   ├── journeys.py             # Schemas de journeys
│   └── tracking.py             # Schemas de actividades
└── main.py                     # Aplicacion FastAPI
```

## Endpoints

### Enrollments

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `POST` | `/api/v1/enrollments/` | Inscribir usuario autenticado en un journey |
| `GET` | `/api/v1/enrollments/me` | Obtener mis inscripciones |

### Tracking

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `POST` | `/api/v1/tracking/event` | Registrar actividad y calcular puntos |

### System

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/health` | Health check del servicio |

## Autenticacion

Todos los endpoints requieren un JWT valido en el header:

```http
Authorization: Bearer <access_token>
```

El `user_id` se obtiene automaticamente del token JWT, nunca del payload.

## Rate Limiting

| Endpoint | Limite | Razon |
|----------|--------|-------|
| `POST /tracking/event` | 60/min | Prevenir abuso de puntos |
| Otros endpoints | 200/min | Limite por defecto |

## Modelo de Datos

### Journeys Schema (PostgreSQL)

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

- Los usuarios solo pueden ver/modificar sus propios datos
- Los journeys son visibles para miembros de la organizacion
- El ledger de puntos es solo lectura para usuarios

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

## Ejecucion

### Desarrollo

```bash
poetry run uvicorn services.journey_service.main:app --reload --port 8002
```

### Documentacion

- Swagger UI: http://localhost:8002/api/v1/docs
- OpenAPI JSON: http://localhost:8002/api/v1/openapi.json

## Variables de Entorno

Hereda de `CommonSettings`:

```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
JWT_ALGORITHM=HS256
```

Especificas del servicio:

```env
TYPEFORM_SECRET=your-typeform-webhook-secret  # Para webhooks de Typeform
```

## Tests

```bash
pytest services/journey_service/tests/
```
