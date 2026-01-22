#!/bin/bash

# Nombre del directorio raíz
#ROOT="oasis-api"
#mkdir -p $ROOT
#cd $ROOT

# 1. Crear carpeta común para lógica compartida (Base de Datos, Auth, Schemas)
mkdir -p common/auth common/database common/schemas
touch common/__init__.py
touch common/auth/__init__.py
touch common/database/__init__.py
touch common/schemas/__init__.py

# Archivos base de lógica compartida
touch common/auth/security.py
touch common/database/client.py
touch common/schemas/base.py

# 2. Definir los microservicios del ecosistema Oasis
SERVICES=("ai-service" "crm-service" "journey-service" "content-service" "community-service" "event-service" "auth-service")

# 3. Crear estructura para cada servicio con centralizador api/v1
for SERVICE in "${SERVICES[@]}"
do
    # Crear rutas de directorios: API (con v1 y endpoints), Core, y Tests
    mkdir -p services/$SERVICE/api/v1/endpoints
    mkdir -p services/$SERVICE/core
    mkdir -p services/$SERVICE/tests
    mkdir -p services/$SERVICE/schemas
    mkdir -p services/$SERVICE/crud

    # Crear archivos __init__.py para que Python los reconozca como paquetes
    touch services/$SERVICE/__init__.py
    touch services/$SERVICE/api/__init__.py
    touch services/$SERVICE/api/v1/__init__.py
    touch services/$SERVICE/api/v1/endpoints/__init__.py
    touch services/$SERVICE/core/__init__.py
    touch services/$SERVICE/tests/__init__.py
    touch services/$SERVICE/schemas/__init__.py
    touch services/$SERVICE/crud/__init__.py

    # Archivos fundamentales del microservicio
    touch services/$SERVICE/main.py            # Punto de entrada FastAPI
    touch services/$SERVICE/api/v1/api.py      # CENTRALIZADOR de rutas v1
    touch services/$SERVICE/core/config.py     # Configuración Pydantic
    touch services/$SERVICE/Dockerfile         # Configuración para Cloud Run
    touch services/$SERVICE/requirements.txt   # Para dependencias específicas si no usas Poetry global

    echo "🏗️  Estructura profesional creada para: $SERVICE"
done

# 4. Crear carpeta de recursos estáticos (ej: logo para el README)
mkdir -p public

# 5. Archivos raíz del proyecto
#touch docker-compose.yml
touch .env.example
touch .gitignore
touch pyproject.toml
touch README.md
touch .pre-commit-config.yaml

echo "✅ Proyecto 'oasis-api' inicializado correctamente con todos los archivos __init__.py."
