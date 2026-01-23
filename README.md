<p align="center">
  <img src="public/favicon.png" width="120" alt="OASIS Logo">
</p>

# OASIS API 🌴

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

**OASIS API** es el motor de microservicios que alimenta el ecosistema digital de la **Fundación Summer**. Diseñado con una arquitectura **Multi-Tenant (B2B/B2C)**, gestiona de forma segura identidades, organizaciones y el viaje emocional de los participantes mediante IA y gamificación.

## ✨ Características Principales

* 🏢 **Arquitectura Multi-Tenant**: Soporte nativo para Organizaciones (Sponsors/Empresas) y Comunidad (B2C) en una misma instancia.
* 🛡️ **Seguridad Contextual**: Autenticación vía Supabase Auth con validación de contexto `X-Organization-ID`.
* 👁️ **Sistema de Auditoría**: Logs inmutables de seguridad y cumplimiento normativo (ISO/GDPR ready).
* 🤖 **AI Agents**: Agentes especializados en *Coaching* y *Mentoría* utilizando Google Gemini.
* 🎮 **OASIS Journey**: Motor de gamificación con niveles y puntos (XP).
* 🚀 **Scalability**: Arquitectura desacoplada lista para **Google Cloud Run**.

## 🏗️ Arquitectura del Sistema

El ecosistema está fragmentado en microservicios especializados para garantizar alta disponibilidad:
```text
               [ Frontend Next.js ]
                       ⬆
              [ API Gateway /v1/ ]
     ┌─────────────┬─────────────┬─────────────┐
[ Auth-Service ] [ Journey-Service ] [ AI-Service ] ...
     └─────────────┴─────────────┴─────────────┘
                       ⬆
               [ Supabase DB / RAG ]
          (Auth, Profiles, Audit, Vectors)
```

## 🛠️ Stack Tecnológico

- Lenguaje: Python 3.11+
- Framework: FastAPI (Asíncrono)
- Base de Datos: PostgreSQL + pgvector (vía Supabase)
- Auth: Supabase Auth (JWT) + RLS Policies
- IA: Google Gemini 1.5 Flash / Pro
- Calidad: Ruff (Linting & Formatting) y Pre-commit hooks
- Infraestructura: Docker + Google Cloud Run

## 🚀 Inicio Rápido

### Requisitos Previos

1. Instancia de Supabase activa (Local o Cloud).
2. Python 3.11+ y Poetry instalado.
3. Variables de entorno configuradas (.env).

### Instalación

Clonar y configurar:
```bash
git clone https://github.com/tu-usuario/oasis-api.git
cd oasis-api
cp .env.example .env
```

Instalar dependencias:
```bash
poetry install
pre-commit install
```

Inicializar Base de Datos (Seed):

> Carga usuarios, roles y organizaciones por defecto.
```bash
python -m scripts.create_users
```

Ejecutar Servidor de Desarrollo:
```bash
poetry run uvicorn services.auth_service.main:app --reload
```

Documentación interactiva disponible en: http://localhost:8000/api/v1/docs

## 👥 Matriz de Seguridad y Roles

El sistema maneja dos niveles de roles: Nivel Plataforma (Global) y Nivel Organización (Contextual).

1. **Nivel Plataforma (Global)**

| Rol | Alcance |
|-----|---------|
| Platform Admin | "God Mode". Puede ver todos los logs de auditoría, gestionar cualquier organización y realizar tareas de mantenimiento global. |
| Usuario Estándar | Acceso limitado a sus propios datos y a las organizaciones donde es miembro. |

2. **Nivel Organización (Contextual)**

> Estos permisos aplican solo dentro de la organización especificada en el header `X-Organization-ID`.

| Rol | Alcance |
|-----|---------|
| Owner | Dueño de la instancia B2B. Gestión de facturación, configuración de marca y gestión de admins. |
| Admin | Gestión operativa: invitar miembros, ver reportes y gestionar equipos. |
| Facilitador | (Staff) Puede gestionar eventos y ver progreso de participantes asignados. |
| Participante | (Usuario final) Acceso a journeys, contenido y herramientas de bienestar. |

## 📡 Integración API

Para consumir endpoints protegidos por organización (ej: invitar miembro), se deben enviar los siguientes headers:
```http
Authorization: Bearer <access_token>
X-Organization-ID: <uuid-de-la-organizacion>
```

<p align="center">Hecho con 💙 para la <strong>Fundación Summer</strong> • 2026</p>
