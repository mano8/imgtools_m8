"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter
from sqlmodel import text

from auth_user_service.core.config import settings
from auth_user_service.core.deps import get_redis_client
from auth_user_service.core.engine_sync import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", summary="Service health and infrastructure status")
def health_check() -> dict[str, Any]:
    """Return effective operating state including Redis and database reachability.

    Useful for monitoring and for diagnosing silent degradation when TOKEN_MODE
    is ``stateful`` or ``hybrid`` but Redis is unavailable.
    """
    redis_required = settings.TOKEN_MODE != "stateless"

    redis_ok = False
    if redis_required:
        redis_ok = get_redis_client() is not None
    else:
        redis_ok = True  # not required; report as OK to avoid false alarms

    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    effective_mode = settings.TOKEN_MODE
    if redis_required and not redis_ok:
        effective_mode = "stateless_degraded"

    overall = "ok" if (redis_ok and db_ok) else "degraded"

    return {
        "status": overall,
        "token_mode": settings.TOKEN_MODE,
        "effective_mode": effective_mode,
        "redis": "ok" if redis_ok else "unavailable",
        "database": "ok" if db_ok else "unavailable",
        "revocation_available": redis_ok and redis_required,
        "rate_limiting_available": redis_ok and redis_required,
    }
