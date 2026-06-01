"""auth_user_service/fastapi/main.py"""

import asyncio
import logging
import time as _time
import uuid
import uvicorn

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from auth_user_service.routes import api_router
from auth_user_service.core.config import settings
from auth_sdk_m8.observability import metrics as _metrics
from auth_sdk_m8.observability.middleware import MetricsMiddleware

_logger = logging.getLogger(__name__)

_FLUSH_INTERVAL_SECONDS = 60

_metrics.setup(
    enabled=settings.METRICS_ENABLED,
    groups_str=settings.METRICS_GROUPS,
    api_prefix=settings.API_PREFIX,
)


def _init_degradation_gauges() -> None:
    """Set auth_degradation_mode_active gauge from configured settings at startup."""
    m = _metrics.get()
    if m is None or m.degradation_mode_active is None:
        return
    m.degradation_mode_active.labels(
        control="rate_limit", mode=settings.effective_failure_mode("rate_limit")
    ).set(1)
    m.degradation_mode_active.labels(
        control="refresh_validation",
        mode=settings.effective_failure_mode("refresh_validation"),
    ).set(1)
    m.degradation_mode_active.labels(
        control="session_write", mode=settings.effective_failure_mode("session_write")
    ).set(1)
    m.degradation_mode_active.labels(
        control="access_revocation",
        mode=settings.effective_failure_mode("access_revocation"),
    ).set(1)


_init_degradation_gauges()


def _flush_last_used_at() -> None:
    """Batch-write api_key last_used_at from the Redis write-behind hash to the DB.

    Uses HGETALL + pipeline DELETE for a near-atomic snapshot: any writes that
    arrive in the tiny gap between the two calls are deferred to the next cycle.
    Rows are updated only when the new timestamp is strictly greater, preserving
    the last-writer-wins invariant without dialect-specific SQL (GREATEST).
    """
    from auth_user_service.core.deps import LAST_USED_AT_HASH, get_redis_client
    from auth_user_service.core.engine_sync import engine
    from auth_user_service.db_models.api_keys import ApiKey
    from sqlmodel import Session

    redis = get_redis_client()
    if redis is None:
        return

    with redis.pipeline() as pipe:
        pipe.hgetall(LAST_USED_AT_HASH)
        pipe.delete(LAST_USED_AT_HASH)
        data, _ = pipe.execute()

    if not data:
        return

    with Session(engine) as session:
        for key_id_str, ts_str in data.items():
            try:
                api_key = session.get(ApiKey, uuid.UUID(key_id_str))
                if api_key is None:
                    continue
                new_ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
                current = api_key.last_used_at
                if current is None or current.replace(tzinfo=timezone.utc) < new_ts:
                    api_key.last_used_at = new_ts
                    session.add(api_key)
            except Exception:
                _logger.exception("flush.last_used_at.row_error key_id=%s", key_id_str)
        session.commit()


async def _last_used_at_flush_loop() -> None:
    """Hardened flush loop: shields exceptions, re-raises CancelledError cleanly."""
    while True:
        try:
            await asyncio.sleep(_FLUSH_INTERVAL_SECONDS)
            start = _time.monotonic()
            await asyncio.to_thread(_flush_last_used_at)
            elapsed = _time.monotonic() - start
            m = _metrics.get()
            if m and m.api_key_flush_duration_seconds:
                m.api_key_flush_duration_seconds.observe(elapsed)
        except asyncio.CancelledError:
            _logger.info("flush.last_used_at.shutdown — running final flush")
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(_flush_last_used_at), timeout=5.0
                )
            except Exception:
                _logger.exception("flush.last_used_at.final_flush_error")
            raise
        except Exception:
            _logger.exception("flush.last_used_at.loop_error")


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

    if settings.is_stateless:
        _logger.info(
            "STARTUP: rate_limits login=%d/%dmin (%.2f req/min)"
            " [refresh: inactive in stateless mode]",
            settings.LOGIN_RATE_LIMIT_REQUESTS,
            settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES,
            settings.LOGIN_RATE_LIMIT_REQUESTS
            / float(settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES),
        )
    else:
        _logger.info(
            "STARTUP: rate_limits login=%d/%dmin (%.2f req/min)"
            " refresh=%d/%dmin (%.2f req/min)",
            settings.LOGIN_RATE_LIMIT_REQUESTS,
            settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES,
            settings.LOGIN_RATE_LIMIT_REQUESTS
            / float(settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES),
            settings.REFRESH_RATE_LIMIT_REQUESTS,
            settings.REFRESH_RATE_LIMIT_WINDOW_MINUTES,
            settings.REFRESH_RATE_LIMIT_REQUESTS
            / float(settings.REFRESH_RATE_LIMIT_WINDOW_MINUTES),
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
    flush_task = asyncio.create_task(_last_used_at_flush_loop())
    try:
        yield
    finally:
        flush_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(flush_task), timeout=6.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        from auth_user_service.core.engine_sync import engine

        engine.dispose()


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


_is_production = settings.ENVIRONMENT == "production"

if _is_production and (
    settings.SET_DOCS or settings.SET_REDOC or settings.SET_OPEN_API
):
    raise ValueError(
        "SET_DOCS, SET_REDOC, and SET_OPEN_API cannot be enabled in production "
        "(ENVIRONMENT=production). Set all three to false in your env file."
    )

# In production docs are always disabled. In other environments the per-flag
# overrides (SET_DOCS, SET_REDOC, SET_OPEN_API) apply as usual.
_docs_url = (
    f"{settings.API_PREFIX}/docs" if not _is_production and settings.SET_DOCS else None
)
_redoc_url = (
    f"{settings.API_PREFIX}/redoc"
    if not _is_production and settings.SET_REDOC
    else None
)
_openapi_url = (
    f"{settings.API_PREFIX}/openapi.json"
    if not _is_production and settings.SET_OPEN_API
    else None
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=_openapi_url,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)


def _build_cors_origin_regex(schemes: list) -> str | None:
    """Build a CORSMiddleware allow_origin_regex from a list of URI schemes.

    Only chrome-extension:// is supported. Chrome extension IDs are exactly
    32 lowercase letters. Fails fast at startup for unsupported schemes so
    operators are not silently given an over-permissive CORS policy.
    Returns None when the scheme list is empty (no extension CORS needed).
    """
    if not schemes:
        return None
    parts = []
    for s in schemes:
        if s == "chrome-extension://":
            parts.append(r"chrome-extension://[a-z]{32}")
        else:
            raise ValueError(
                f"CORS_ALLOWED_ORIGIN_SCHEMES: unsupported scheme '{s}'. "
                "Only 'chrome-extension://' is supported in this template."
            )
    # Single anchored group — prevents partial-match bypass.
    return f"^(?:{'|'.join(parts)})$"


_cors_origin_regex = _build_cors_origin_regex(settings.CORS_ALLOWED_ORIGIN_SCHEMES)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=_cors_origin_regex,
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
