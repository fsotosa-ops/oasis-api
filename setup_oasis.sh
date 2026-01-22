#!/bin/bash

# Nombre del directorio raíz
ROOT="oasis-api"
mkdir -p $ROOT
cd $ROOT

# Crear carpeta común para lógica compartida
mkdir -p common/auth common/database common/schemas
touch common/__init__.py common/auth/security.py common/database/client.py common/schemas/base.py

# Definir los microservicios
SERVICES=("ai-service" "crm-service" "journey-service" "content-service" "community-service" "event-service" "auth-service")

# Crear estructura para cada servicio
for SERVICE in "${SERVICES[@]}"
do
    mkdir -p services/$SERVICE/api/v1/endpoints
    mkdir -p services/$SERVICE/core
    mkdir -p services/$SERVICE/tests
    
    # Archivos base de FastAPI
    touch services/$SERVICE/main.py
    touch services/$SERVICE/api/v1/api.py
    touch services/$SERVICE/core/config.py
    touch services/$SERVICE/Dockerfile
    touch services/$SERVICE/requirements.txt
    
    echo "Instalando estructura para: $SERVICE"
done

# Crear el archivo docker-compose para orquestación local
touch docker-compose.yml
touch .env.example

echo "✅ Estructura de oasis-api creada con éxito."