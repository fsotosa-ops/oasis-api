# common/middleware/rate_limit.py
"""
Rate limiting middleware for OASIS services.

Provides protection against abuse and DoS attacks using slowapi.

Usage:
    from common.middleware import setup_rate_limiting, limiter

    # In main.py:
    setup_rate_limiting(app)

    # In endpoints (optional, for custom limits):
    @router.post("/heavy-operation")
    @limiter.limit("10/minute")
    async def heavy_operation(request: Request, ...):
        ...

Configuration via environment variables:
    RATE_LIMIT_ENABLED=true
    RATE_LIMIT_DEFAULT="200/minute"
    RATE_LIMIT_STORAGE_URL="redis://localhost:6379"  # Optional, uses memory by default
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from common.schemas.responses import ErrorDetail, OasisErrorResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = True
    default_limit: str = "200/minute"  # Global default
    storage_url: str | None = None  # None = in-memory, "redis://..." for Redis

    # Endpoint-specific defaults
    auth_limit: str = "20/minute"  # Login, register (prevent brute force)
    write_limit: str = "100/minute"  # POST, PUT, DELETE
    read_limit: str = "300/minute"  # GET requests

    # Headers
    headers_enabled: bool = True  # Include X-RateLimit-* headers


# =============================================================================
# Key Functions (identify who to rate limit)
# =============================================================================


def get_user_or_ip(request: Request) -> str:
    """
    Get rate limit key: user_id if authenticated, IP otherwise.

    This ensures:
    - Authenticated users get their own bucket (by user_id)
    - Anonymous users are limited by IP
    """
    # Check if user was set by auth middleware
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.get('id', get_remote_address(request))}"

    # Check Authorization header for JWT (extract sub claim)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        # Don't decode JWT here, just use token hash as key
        # This groups requests by token without validation overhead
        token = auth_header[7:]
        return f"token:{hash(token) % 10**10}"

    # Fallback to IP
    return f"ip:{get_remote_address(request)}"


def get_ip_only(request: Request) -> str:
    """Always use IP address (for auth endpoints before login)."""
    return f"ip:{get_remote_address(request)}"


# =============================================================================
# Limiter Instance
# =============================================================================

# Global limiter instance - configured on setup
limiter = Limiter(
    key_func=get_user_or_ip,
    default_limits=["200/minute"],
    headers_enabled=True,
    strategy="fixed-window",  # or "moving-window" for smoother limiting
)


# =============================================================================
# Exception Handler
# =============================================================================


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.

    Returns a consistent OasisErrorResponse format.
    """
    logger.warning(
        f"Rate limit exceeded: {get_user_or_ip(request)} on {request.url.path}"
    )

    retry_after = exc.detail.split("per")[0].strip() if exc.detail else "1 minute"

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=OasisErrorResponse(
            error=ErrorDetail(
                code="rate_limit_exceeded",
                message=f"Demasiadas solicitudes. Intenta de nuevo en {retry_after}.",
            )
        ).model_dump(),
        headers={
            "Retry-After": "60",  # Suggest retry after 60 seconds
            "X-RateLimit-Limit": exc.detail or "200/minute",
        },
    )


# =============================================================================
# Setup Function
# =============================================================================


def setup_rate_limiting(
    app: FastAPI,
    config: RateLimitConfig | None = None,
) -> None:
    """
    Configure rate limiting for a FastAPI application.

    Args:
        app: FastAPI application instance
        config: Optional configuration (uses defaults if not provided)

    Example:
        app = FastAPI()
        setup_rate_limiting(app, RateLimitConfig(default_limit="100/minute"))
    """
    if config is None:
        config = RateLimitConfig()

    if not config.enabled:
        logger.info("Rate limiting is disabled")
        return

    # Configure storage backend
    if config.storage_url:
        # Redis storage for distributed rate limiting
        try:
            from slowapi.middleware import SlowAPIMiddleware

            limiter._storage_url = config.storage_url
            app.add_middleware(SlowAPIMiddleware)
            logger.info(f"Rate limiting using Redis: {config.storage_url}")
        except ImportError:
            logger.warning("Redis not available, using in-memory storage")

    # Update default limits
    limiter._default_limits = [config.default_limit]
    limiter._headers_enabled = config.headers_enabled

    # Attach limiter to app state
    app.state.limiter = limiter

    # Register exception handler
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    logger.info(f"Rate limiting enabled: {config.default_limit} (default)")


# =============================================================================
# Decorator Helpers
# =============================================================================


def limit_auth(limit: str = "20/minute") -> Callable:
    """
    Rate limit decorator for authentication endpoints.

    Uses IP-only key function to prevent brute force attacks.

    Usage:
        @router.post("/login")
        @limit_auth("10/minute")
        async def login(request: Request, ...):
            ...
    """
    return limiter.limit(limit, key_func=get_ip_only)


def limit_write(limit: str = "100/minute") -> Callable:
    """Rate limit decorator for write operations (POST, PUT, DELETE)."""
    return limiter.limit(limit)


def limit_read(limit: str = "300/minute") -> Callable:
    """Rate limit decorator for read operations (GET)."""
    return limiter.limit(limit)


# =============================================================================
# Shared Limits (for endpoints that share a budget)
# =============================================================================


def limit_shared(limit: str, scope: str) -> Callable:
    """
    Rate limit decorator with shared scope across endpoints.

    All endpoints with the same scope share the rate limit budget.

    Usage:
        @router.post("/upload")
        @limit_shared("10/hour", scope="heavy_operations")
        async def upload(...):

        @router.post("/export")
        @limit_shared("10/hour", scope="heavy_operations")
        async def export(...):
        # Both share the 10/hour limit
    """
    return limiter.limit(limit, scope=scope)
