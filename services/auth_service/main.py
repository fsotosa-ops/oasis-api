# services/auth_service/main.py
"""
Auth Service - Identity & Access Management for OASIS Platform.

This service handles:
- User authentication (login, register, tokens)
- User profile management
- Organization management
- Membership and role management
- Audit logging
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_settings
from common.database.client import (
    close_db_connections,
    health_check,
    verify_connection,
)
from common.exceptions import OasisException, oasis_exception_handler
from common.middleware import RateLimitConfig, setup_rate_limiting
from services.auth_service.api.v1.api import api_router
from services.auth_service.core.config import settings

global_settings = get_settings()


# ============================================================================
# Application Lifecycle
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.

    Startup:
    - Verify database connection
    - Pre-warm connection pool

    Shutdown:
    - Close database connections
    - Cleanup resources
    """
    # === STARTUP ===
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"   Environment: {global_settings.ENVIRONMENT}")

    try:
        await verify_connection()
        print("✅ Database connection verified")
    except Exception as e:
        print(f"⚠️  Database connection warning: {e}")
        # Don't fail startup - allow service to start and retry later

    yield

    # === SHUTDOWN ===
    print("👋 Shutting down...")
    await close_db_connections()
    print("✅ Shutdown complete")


# ============================================================================
# API Documentation
# ============================================================================

description_text = """
## 🔐 OASIS Identity & Access Management

Multi-tenant authentication and authorization service for the OASIS platform.

### Authentication Flow

1. **Register** - Create a new account
2. **Login** - Get access and refresh tokens
3. **Use tokens** - Include `Authorization: Bearer <token>` in requests
4. **Refresh** - Use refresh token to get new access token

### Multi-Tenant Context

For organization-specific operations, include the header:
```
X-Organization-ID: <uuid>
```

### Role Hierarchy

**Platform Level:**
- `Platform Admin` - God mode, access to everything

**Organization Level:**
- `owner` - Full control of the organization
- `admin` - Operational management, can invite members
- `facilitador` - Staff, can view participant progress
- `participante` - End user, access to content

### API Sections

- **Auth** - Login, register, token management
- **Users** - User profile and account management
- **Organizations** - Organization and membership CRUD
- **Audit** - Activity logs and compliance
"""

tags_metadata = [
    {
        "name": "Auth",
        "description": "Authentication: login, register, tokens, password management",
    },
    {
        "name": "Users",
        "description": "User management: profiles, platform admin operations",
    },
    {
        "name": "Organizations",
        "description": "Organization and membership management",
    },
    {
        "name": "Audit",
        "description": "Audit logs and activity tracking",
    },
]


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=description_text,
    openapi_tags=tags_metadata,
    openapi_url=f"{global_settings.API_V1_STR}/openapi.json",
    docs_url=f"{global_settings.API_V1_STR}/docs",
    redoc_url=f"{global_settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)


# ============================================================================
# Middleware
# ============================================================================

if global_settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in global_settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ============================================================================
# Exception Handlers & Rate Limiting
# ============================================================================

# Custom exception handler for consistent error responses
app.add_exception_handler(OasisException, oasis_exception_handler)

# Rate limiting - auth endpoints get stricter limits
setup_rate_limiting(
    app,
    RateLimitConfig(
        enabled=True,
        default_limit="200/minute",
        auth_limit="20/minute",  # Stricter for login/register
        write_limit="100/minute",
        read_limit="300/minute",
    ),
)


# ============================================================================
# Routes
# ============================================================================

app.include_router(api_router, prefix=global_settings.API_V1_STR)


# ============================================================================
# Health Check
# ============================================================================


@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check_endpoint(response: Response):
    """
    Service health check.

    Returns:
    - 200 OK: Service is healthy
    - 503 Service Unavailable: Database connection issues
    """
    health = await health_check()

    result = {
        "status": "healthy" if health["healthy"] else "unhealthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "database": "connected" if health["healthy"] else "disconnected",
    }

    if not health["healthy"]:
        result["error"] = health.get("error")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return result


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint redirect to docs."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": f"{global_settings.API_V1_STR}/docs",
    }
