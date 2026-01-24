import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from common.database.client import close_db_connections, verify_connection
from common.exceptions import OasisException, oasis_exception_handler
from common.middleware import RateLimitConfig, setup_rate_limiting
from services.journey_service.api.v1.api import api_router
from services.journey_service.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the Journey Service."""
    logger.info(f"Starting {settings.PROJECT_NAME}...")

    # Verify database connection on startup
    try:
        await verify_connection()
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info(f"Stopping {settings.PROJECT_NAME}...")
    await close_db_connections()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    description="""
    Microservicio encargado de la experiencia del usuario, progresión y gamificación.

    ## Autenticación
    Todos los endpoints requieren un JWT válido en el header
    `Authorization: Bearer <token>`.

    ## Endpoints principales
    - **Enrollments**: Inscripciones en journeys
    - **Tracking**: Registro de actividades y gamificación
    """,
)

# Register custom exception handler
app.add_exception_handler(OasisException, oasis_exception_handler)

# Setup rate limiting
setup_rate_limiting(
    app,
    RateLimitConfig(
        enabled=True,
        default_limit="200/minute",
        write_limit="100/minute",
        read_limit="300/minute",
    ),
)

# Include API routes
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "ok", "service": "journey_service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
