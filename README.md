<p align="center">
  <img src="public/favicon.png" width="120" alt="OASIS Logo">
</p>

# OASIS API 🌴

<p align="center">
  <strong>Plataforma de Salud Mental y Resiliencia impulsada por IA</strong>
</p>

<p align="center">
  <a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI"></a>
  <a href="https://supabase.com"><img src="https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/python-3.11+-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54" alt="Python Version"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/Linter-Ruff-CC99FF?style=for-the-badge" alt="Ruff"></a>
</p>

---

**OASIS API** es el motor de microservicios que alimenta el portal digital de la **Fundación Summer**. Diseñado con una arquitectura *Cloud-Native*, gestiona el viaje emocional de los participantes a través de gamificación, soporte de IA en tiempo real y métricas de impacto para organizaciones.

## ✨ Características Principales

* 🤖 **AI Agents**: Agentes especializados en *Coaching* y *Mentoría* utilizando Google Gemini.
* 🎮 **OASIS Journey**: Motor de gamificación con niveles, puntos (XP) y hitos tipo Salesforce Trailhead.
* 📊 **CRM Analytics**: Monitoreo de salud emocional con cálculo de *Health Score* y NPS dinámico.  
* 🔒 **Enterprise Security**: Autenticación integrada con Supabase y políticas RLS granulares.
* 🚀 **Scalability**: Arquitectura desacoplada lista para **Google Cloud Run**.

## 🏗️ Arquitectura del Sistema

El ecosistema está fragmentado en microservicios especializados para garantizar alta disponibilidad y escalado independiente:

```text
               [ Frontend Next.js ]
                       ⬆
              [ API Gateway /v1/ ]  
     ┌─────────────┬─────────────┬─────────────┐
[ AI-Service ]   [ CRM-Service ]   [ Journey-Service ] ...
     └─────────────┴─────────────┴─────────────┘
                       ⬆
               [ Supabase DB / RAG ]
```

## 🛠️ Stack Tecnológico

- **Lenguaje**: Python 3.11+
- **Framework**: FastAPI (Asíncrono) 
- **Base de Datos**: PostgreSQL + pgvector (vía Supabase)
- **IA**: Google Gemini 1.5 Flash / Pro
- **Calidad**: Ruff (Linting & Formatting)
- **Infraestructura**: Docker + Google Cloud Run

## 🚀 Inicio Rápido

### Requisitos Previos

1. Instancia de Supabase activa.
2. API Key de Google AI (Gemini).
3. Poetry instalado.

### Instalación 

Clonar y acceder:

```bash
git clone https://github.com/tu-usuario/oasis-api.git
cd oasis-api
```

Configurar entorno:

```bash  
cp .env.example .env
# Edita .env con tus credenciales
```

Instalar dependencias y hooks:

```bash
poetry install  
pre-commit install
```

## 👥 Matriz de Roles

| Rol          | Alcance                                                               |
|--------------|----------------------------------------------------------------------|
| Participante | Acceso a su propio viaje, foro comunitario y recursos de bienestar. |
| Gestor       | Administración de habitantes, carga de recursos y gestión de eventos/CRM. |
| Visitante    | Acceso público a contenido de awareness y recursos gratuitos.       |
| Super Admin  | Control total de configuración, roles de sistema y logs de IA.      |

## 🧪 Desarrollo y Calidad

Utilizamos Ruff para mantener el código limpio y unificado bajo un solo estándar.

- Analizar código: `ruff check .`  
- Formatear automáticamente: `ruff format .`
- Ejecutar pruebas: `pytest`

<p align="center">Hecho con 💙 para la <strong>Fundación Summer</strong> • 2026</p>
