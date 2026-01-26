<p align="center">
  <img src="public/favicon.png" width="120" alt="OASIS Logo">
</p>

# OASIS API

<p align="center">
  <strong>Plataforma Multi-Tenant de Salud Mental y Resiliencia impulsada por IA</strong>
</p>

<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI"></a>
  <a href="https://supabase.com"><img src="https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python Version"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/Linter-Ruff-CC99FF?style=for-the-badge" alt="Ruff"></a>
</p>

---

**OASIS API** es el motor de microservicios que alimenta el ecosistema digital de la **Fundacion Summer**. Disenado con una arquitectura **Multi-Tenant (B2B/B2C)**, gestiona de forma segura identidades, organizaciones y el viaje emocional de los participantes mediante IA y gamificacion.

## Caracteristicas Principales

- **Arquitectura Multi-Tenant**: Soporte nativo para Organizaciones (Sponsors/Empresas) y Comunidad (B2C) en una misma instancia
- **Seguridad en Profundidad**: Autenticacion JWT + RLS Policies + Rate Limiting
- **Sistema de Auditoria**: Logs inmutables de seguridad y cumplimiento normativo (ISO/GDPR ready)
- **AI Agents**: Agentes especializados en Coaching y Mentoria utilizando Google Gemini
- **Journey Engine**: Motor de gamificacion con niveles, puntos y recompensas
- **Escalabilidad**: Arquitectura desacoplada lista para Google Cloud Run

## Arquitectura del Sistema

```
                      [ Frontend Next.js ]
                              |
                     [ API Gateway /v1/ ]
       +----------+-----------+-----------+----------+
       |          |           |           |          |
[ Auth      [ Journey    [ AI        [ Webhook      |
  Service ]   Service ]    Service ]   Service ]    |
       |          |           |           |          |
       +----------+-----------+-----------+----------+
                              |
                      [ Supabase DB ]
               (Auth, Profiles, Journeys, Vectors)
                              |
                              |
       +----------------------+----------------------+
       |                                             |
[ Typeform ]                                   [ Stripe ]
(Encuestas)                                    (Pagos)
```

## Microservicios

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| **auth_service** | 8001 | Identidad, autenticacion, organizaciones y auditoria |
| **journey_service** | 8002 | Experiencia, progresion, gamificacion y backoffice admin |
| **ai_service** | 8003 | Agentes de coaching con Gemini |
| **webhook_service** | 8004 | Gateway universal de webhooks (Typeform, Stripe, etc.) |

### Endpoints Principales

**Auth Service** (`/api/v1/`)
- `/auth/*` - Login, registro, tokens
- `/users/*` - Gestion de usuarios y perfiles
- `/organizations/*` - CRUD de organizaciones y miembros
- `/audit/*` - Logs de auditoria (admin)

**Journey Service** (`/api/v1/`)
- `/journeys/*` - Lectura de journeys (usuarios)
- `/enrollments/*` - Inscripciones y progreso
- `/me/*` - Gamificacion: stats, rewards, leaderboard
- `/tracking/*` - Registro de actividades y eventos externos
- `/admin/journeys/*` - CRUD journeys y steps (backoffice)
- `/admin/levels/*` - Configuracion de niveles (backoffice)
- `/admin/rewards/*` - Catalogo de recompensas (backoffice)
- `/admin/enrollments` - Analytics de inscripciones (backoffice)

**Webhook Service** (`/api/v1/`)
- `POST /webhooks/{provider}` - Recibir webhook de cualquier proveedor
- `GET /webhooks/providers` - Listar proveedores y estado
- `POST /webhooks/dlq/retry` - Reintentar eventos fallidos

## Stack Tecnologico

| Categoria | Tecnologia |
|-----------|------------|
| Lenguaje | Python 3.11+ |
| Framework | FastAPI (Asincrono) |
| Base de Datos | PostgreSQL + pgvector (via Supabase) |
| Autenticacion | Supabase Auth (JWT) + RLS Policies |
| Rate Limiting | slowapi (in-memory / Redis) |
| IA | Google Gemini 1.5 Flash / Pro |
| Calidad | Ruff (Linting & Formatting) + Pre-commit |
| Infraestructura | Docker + Google Cloud Run |

## Inicio Rapido

### Requisitos Previos

1. Instancia de Supabase activa (Local o Cloud)
2. Python 3.11+ y Poetry instalado
3. Variables de entorno configuradas (.env)

### Instalacion

```bash
# Clonar repositorio
git clone https://github.com/tu-usuario/oasis-api.git
cd oasis-api

# Configurar variables de entorno
cp .env.example .env

# Instalar dependencias
poetry install

# Configurar pre-commit hooks
pre-commit install
```

### Base de Datos

```bash
# Aplicar migraciones (requiere Supabase CLI)
supabase db push

# Cargar datos iniciales
python -m scripts.seed_dev
```

### Ejecutar Servicios

```bash
# Auth Service (puerto 8001)
poetry run uvicorn services.auth_service.main:app --reload --port 8001

# Journey Service (puerto 8002)
poetry run uvicorn services.journey_service.main:app --reload --port 8002

# Webhook Service (puerto 8004)
poetry run uvicorn services.webhook_service.main:app --reload --port 8004
```

### Documentacion Interactiva

- Auth Service: http://localhost:8001/api/v1/docs
- Journey Service: http://localhost:8002/api/v1/docs
- Webhook Service: http://localhost:8004/api/v1/docs

## Estructura del Proyecto

```
oasis-api/
├── common/                    # Codigo compartido entre servicios
│   ├── auth/
│   │   └── security.py        # JWT validation, role checkers
│   ├── database/
│   │   └── client.py          # Singleton Supabase clients
│   ├── middleware/
│   │   └── rate_limit.py      # Rate limiting centralizado
│   ├── schemas/
│   │   ├── responses.py       # OasisResponse envelope
│   │   └── logs.py            # Audit log schemas
│   ├── config.py              # CommonSettings base
│   ├── errors.py              # ErrorCodes centralizados
│   └── exceptions.py          # OasisException + handlers
├── services/
│   ├── auth_service/          # Identidad y acceso
│   ├── journey_service/       # Gamificacion
│   ├── webhook_service/       # Gateway de webhooks externos
│   └── ai_service/            # Agentes IA
├── supabase/
│   └── migrations/            # SQL migrations
├── scripts/
│   └── seed_dev.py            # Datos de desarrollo
└── pyproject.toml             # Dependencias Poetry
```

## Seguridad

### Defensa en Profundidad

```
1. Rate Limiting     → Proteccion DDoS y abuso
2. JWT Validation    → Autenticacion de identidad
3. Role Checkers     → Autorizacion en backend (Python)
4. Org Isolation     → Verificacion de pertenencia a organizacion
5. RLS Policies      → Autorizacion en base de datos (PostgreSQL)
```

### Aislamiento Multi-Tenant

Todos los endpoints que acceden a recursos de organizacion verifican:

```python
# 1. Usuario autenticado (JWT)
# 2. Membresia activa en la organizacion (X-Organization-ID)
# 3. Recurso pertenece a la organizacion

OrgMemberRequired()  # Valida 1 y 2
verify_*_belongs_to_org()  # Valida 3
```

Esto previene acceso cross-tenant incluso si un atacante conoce UUIDs de otras organizaciones.

### Rate Limits

| Endpoint | Limite | Proposito |
|----------|--------|-----------|
| `POST /auth/register` | 10/min | Prevenir creacion masiva |
| `POST /auth/login` | 20/min | Prevenir fuerza bruta |
| `POST /auth/password/reset` | 5/min | Prevenir spam de emails |
| `POST /tracking/event` | 60/min | Prevenir abuso de puntos |
| Default | 200/min | Uso general |

### Roles del Sistema

**Nivel Plataforma (Global)**

| Rol | Alcance |
|-----|---------|
| Platform Admin | Acceso total. Gestiona todas las organizaciones y usuarios |
| Usuario Estandar | Acceso a sus datos y organizaciones donde es miembro |

**Nivel Organizacion (Contextual)**

> Requiere header `X-Organization-ID`

| Rol | Alcance |
|-----|---------|
| Owner | Dueno de la org. Facturacion, configuracion, gestion de admins |
| Admin | Gestion operativa: invitar miembros, ver reportes |
| Facilitador | Staff. Gestiona eventos y ve progreso de participantes |
| Participante | Usuario final. Acceso a journeys y contenido |

## Integracion API

### Headers Requeridos

```http
Authorization: Bearer <access_token>
X-Organization-ID: <uuid>  # Solo para endpoints contextuales
```

### Formato de Respuesta

Todas las respuestas siguen el envelope `OasisResponse`:

```json
{
  "success": true,
  "message": "Operacion exitosa",
  "data": { ... },
  "meta": { "pagination": { ... } }
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

## Testing

```bash
# Ejecutar todos los tests
pytest

# Tests de un servicio especifico
pytest services/auth_service/tests/

# Con coverage
pytest --cov=services --cov-report=html
```

## Deployment

### Docker

```bash
# Build
docker build -t oasis-auth -f services/auth_service/Dockerfile .

# Run
docker run -p 8001:8001 --env-file .env oasis-auth
```

### Google Cloud Run

```bash
gcloud run deploy oasis-auth \
  --source services/auth_service \
  --region us-central1 \
  --allow-unauthenticated
```

## Contribucion

1. Fork del repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit con convencion (`git commit -m "feat: agregar nueva funcionalidad"`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

### Convencion de Commits

```
feat:     Nueva funcionalidad
fix:      Correccion de bug
docs:     Documentacion
refactor: Refactorizacion de codigo
test:     Tests
chore:    Tareas de mantenimiento
```

---

<p align="center">
  Hecho con amor para la <strong>Fundacion Summer</strong> | 2026
</p>
