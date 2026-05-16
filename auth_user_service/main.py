"""auth_user_service/fastapi/main.py"""

import logging
import uvicorn

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from auth_user_service.routes import api_router
from auth_user_service.core.config import settings
from auth_sdk_m8.observability import metrics as _metrics
from auth_sdk_m8.observability.middleware import MetricsMiddleware

_logger = logging.getLogger(__name__)

_metrics.setup(
    enabled=settings.METRICS_ENABLED,
    groups_str=settings.METRICS_GROUPS,
    api_prefix=settings.API_PREFIX,
)


def _startup_checks() -> None:
    """Log warnings when required infrastructure is unreachable at startup."""
    from auth_user_service.core.deps import get_redis_client
    from auth_user_service.core.engine_sync import engine
    from sqlmodel import text
    from auth_sdk_m8.core.config import check_config_health

    check_config_health(settings, _logger)

    if settings.requires_redis:
        redis = get_redis_client()
        if redis is None:
            _logger.critical(
                "STARTUP: Redis unreachable but TOKEN_MODE=%s — "
                "rate limiting and token revocation are disabled",
                settings.TOKEN_MODE,
            )
        else:
            _logger.info(
                "STARTUP: Redis connected OK (TOKEN_MODE=%s)", settings.TOKEN_MODE
            )

    if not (settings.AUTH_SERVICE_ROLE == "consumer" and settings.is_stateless):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            _logger.info("STARTUP: Database connected OK")
        except Exception as ex:
            _logger.critical("STARTUP: Database unreachable: %s", ex)


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

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.TOKENS_ENCRYPTION_KEY.get_secret_value(),
    max_age=3600,
    https_only=settings.SESSION_COOKIE_SECURE,
)

if settings.METRICS_ENABLED:
    app.add_middleware(MetricsMiddleware)

app.mount(
    f"{settings.API_PREFIX}/static",
    StaticFiles(directory=settings.STATIC_BASE_PATH),
    name="static",
)

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


@app.exception_handler(StarletteHTTPException)
async def custom_error_handler(
    request: Request, exc: StarletteHTTPException
) -> Response:
    """Redirect OAuth error pages; return JSON for all other HTTP exceptions."""
    from_path = request.url.path
    if any(x in from_path for x in ["login_success", "oauth-callback"]):
        redirect = RedirectResponse(url=request.url_for("google_auth_login"))
        request.session["error"] = str(exc)
        return redirect
    headers = dict(exc.headers) if exc.headers else {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(SQLAlchemyOperationalError)
async def db_unavailable_handler(
    request: Request, exc: SQLAlchemyOperationalError
) -> JSONResponse:
    """Return 503 when the database is unreachable."""
    _logger.critical("db.unavailable path=%s error=%s", request.url.path, exc.orig)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please try again."},
    )


@app.exception_handler(RedisConnectionError)
async def redis_unavailable_handler(
    request: Request, exc: RedisConnectionError
) -> JSONResponse:
    """Return 503 when Redis is unreachable."""
    _logger.warning("redis.unavailable path=%s error=%s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Cache service temporarily unavailable. Please try again."},
    )


if __name__ == "__main__":
    uvicorn.run("auth_user_service.main:app", host="0.0.0.0", port=5378, reload=True)  # nosec B104
