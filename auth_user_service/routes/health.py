"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter
from sqlmodel import text

from auth_user_service.core.config import settings
from auth_user_service.core.deps import get_redis_client, get_redis_degraded_since
from auth_user_service.core.engine_sync import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", summary="Service health and infrastructure status")
def health_check() -> dict[str, Any]:
    """Return effective operating state including Redis and database reachability.

    Useful for monitoring and for diagnosing silent degradation when TOKEN_MODE
    is ``stateful`` or ``hybrid`` but Redis is unavailable.
    """
    redis_required = settings.requires_redis

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

    degraded_since = get_redis_degraded_since()
    circuit_breaker_open = redis_required and not redis_ok

    degradation_modes = {
        "rate_limit": settings.effective_failure_mode("rate_limit"),
        "refresh_validation": settings.effective_failure_mode("refresh_validation"),
        "session_write": settings.effective_failure_mode("session_write"),
        "access_revocation": settings.effective_failure_mode("access_revocation"),
    }

    return {
        "status": overall,
        "token_mode": settings.TOKEN_MODE,
        "effective_mode": effective_mode,
        "redis": "ok" if redis_ok else "unavailable",
        "circuit_breaker": "open" if circuit_breaker_open else "closed",
        "database": "ok" if db_ok else "unavailable",
        "revocation_available": redis_ok and redis_required,
        "rate_limiting_available": redis_ok and redis_required,
        "degraded_since": degraded_since.isoformat() if degraded_since else None,
        "degradation_modes": degradation_modes,
    }
