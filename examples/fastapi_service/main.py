"""fastapi_service/fastapi/main.py"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_service.app.main import api_router
from fastapi_service.core.config import settings
from auth_sdk_m8.observability import metrics as _metrics
from auth_sdk_m8.observability.middleware import MetricsMiddleware

# pylint: disable=line-too-long

_logger = logging.getLogger(__name__)

_metrics.setup(
    enabled=settings.METRICS_ENABLED,
    groups_str=settings.METRICS_GROUPS,
    api_prefix=settings.API_PREFIX,
)


def _startup_checks() -> None:
    """Log env-var consistency warnings and verify Redis when needed."""
    from auth_sdk_m8.core.config import check_config_health

    check_config_health(settings, _logger)

    if settings.requires_redis:
        try:
            from fastapi_service.core.deps import get_redis_client  # type: ignore[import]

            redis = get_redis_client()
            if redis is None:
                _logger.critical(
                    "STARTUP: Redis unreachable but TOKEN_MODE=%s — "
                    "token revocation checks are disabled",
                    settings.TOKEN_MODE,
                )
            else:
                _logger.info(
                    "STARTUP: Redis connected OK (TOKEN_MODE=%s)", settings.TOKEN_MODE
                )
        except ImportError:
            _logger.debug("STARTUP: no Redis dep module — skipping Redis check")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup_checks()
    yield


def custom_generate_unique_id(route: APIRoute) -> str:
    """
    Generate a unique identifier for a given API route.

    Args:
        route (APIRoute):
            The API route for which to generate the unique identifier.

    Returns:
        str:
            A unique identifier string composed of the route's
            first tag and name.
    """
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=(
        f"{settings.API_PREFIX}/openapi.json" if settings.SET_OPEN_API else None
    ),
    docs_url=f"{settings.API_PREFIX}/docs" if settings.SET_DOCS else None,
    redoc_url=f"{settings.API_PREFIX}/redoc" if settings.SET_REDOC else None,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=3600,  # cache preflight requests for 1 hour
)

if settings.METRICS_ENABLED:
    app.add_middleware(MetricsMiddleware)


def custom_openapi(current_app: FastAPI):
    """Custom openapi"""
    if current_app.openapi_schema:
        return current_app.openapi_schema
    schema = get_openapi(
        title="M8 API",
        version="1.0.0",
        description="Microservice for m8 dashboard and stats",
        routes=current_app.routes,
    )
    # Update tokenUrl to point to external auth service
    # "http://127.0.0.1:9000/user/login/access-token"
    schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"][
        "password"
    ]["tokenUrl"] = f"{settings.BACKEND_HOST}{settings.AUTH_PREFIX}/login/access-token"
    current_app.openapi_schema = schema
    return current_app.openapi_schema


app.openapi = lambda: custom_openapi(app)

app.mount("/static", StaticFiles(directory=settings.STATIC_BASE_PATH), name="static")

app.include_router(api_router, prefix=settings.API_PREFIX)

if settings.METRICS_ENABLED:

    @app.get(
        f"{settings.API_PREFIX}/metrics",
        include_in_schema=False,
        tags=["observability"],
    )
    def metrics_endpoint() -> Response:
        """Expose Prometheus metrics."""
        content, content_type = _metrics.render()
        return Response(content=content, media_type=content_type)
