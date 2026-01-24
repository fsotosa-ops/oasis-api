# Journey Service

**Motor de Experiencia, Progresion y Gamificacion para OASIS**

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
│       ├── api.py                # Router principal
│       └── endpoints/
│           ├── journeys.py       # CRUD de journeys
│           ├── enrollments.py    # Inscripciones y progreso
│           ├── tracking.py       # Registro de actividades
│           └── gamification.py   # Stats, rewards, leaderboard
├── core/
│   └── config.py                 # Configuracion (hereda CommonSettings)
├── crud/
│   ├── enrollments.py            # Operaciones de inscripciones
│   ├── journeys.py               # Operaciones de journeys
│   └── gamification.py           # Operaciones de gamificacion
├── logic/
│   └── gamification.py           # Calculo de puntos y niveles
├── schemas/
│   ├── enrollments.py            # Schemas de inscripciones
│   ├── journeys.py               # Schemas de journeys
│   ├── tracking.py               # Schemas de actividades
│   └── gamification.py           # Schemas de stats y rewards
└── main.py                       # Aplicacion FastAPI
```

## Endpoints

### Journeys

| Metodo | Endpoint | Descripcion | Auth |
|--------|----------|-------------|------|
| `GET` | `/journeys/` | Listar journeys de mi organizacion | Member |
| `GET` | `/journeys/{id}` | Detalle de journey con steps | User |
| `GET` | `/journeys/{id}/steps` | Steps ordenados de un journey | User |

### Enrollments

| Metodo | Endpoint | Descripcion | Auth |
|--------|----------|-------------|------|
| `POST` | `/enrollments/` | Inscribirse en un journey | User |
| `GET` | `/enrollments/me` | Mis inscripciones | User |
| `GET` | `/enrollments/{id}` | Detalle de inscripcion con progreso | Owner |
| `GET` | `/enrollments/{id}/progress` | Progreso detallado por steps | Owner |
| `POST` | `/enrollments/{id}/complete` | Marcar journey como completado | Owner |
| `POST` | `/enrollments/{id}/drop` | Abandonar journey | Owner |
| `POST` | `/enrollments/{id}/resume` | Retomar journey abandonado | Owner |

### Gamification

| Metodo | Endpoint | Descripcion | Auth |
|--------|----------|-------------|------|
| `GET` | `/me/stats` | Puntos, nivel, progreso general | User |
| `GET` | `/me/rewards` | Mis insignias/badges | User |
| `GET` | `/me/activity` | Historial de actividades | User |
| `GET` | `/me/points-history` | Historial de puntos | User |
| `GET` | `/me/leaderboard` | Ranking de usuarios | User |
| `GET` | `/me/levels` | Niveles disponibles | User |

### Tracking

| Metodo | Endpoint | Descripcion | Auth |
|--------|----------|-------------|------|
| `POST` | `/tracking/event` | Registrar actividad y calcular puntos | User |

### System

| Metodo | Endpoint | Descripcion |
|--------|----------|-------------|
| `GET` | `/health` | Health check del servicio |

## Autenticacion

Todos los endpoints requieren un JWT valido:

```http
Authorization: Bearer <access_token>
```

Para endpoints de organizacion, agregar:

```http
X-Organization-ID: <uuid>
```

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

## Ejecucion

### Desarrollo

```bash
poetry run uvicorn services.journey_service.main:app --reload --port 8002
```

### Documentacion

- Swagger UI: http://localhost:8002/api/v1/docs
- ReDoc: http://localhost:8002/api/v1/redoc

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
TYPEFORM_SECRET=your-typeform-webhook-secret
```

## Tests

```bash
pytest services/journey_service/tests/
```
