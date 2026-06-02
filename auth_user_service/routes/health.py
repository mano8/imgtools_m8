"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter
from sqlmodel import text

from auth_user_service.core.config import settings
from auth_user_service.core.deps import get_redis_client, get_redis_degraded_since
from auth_user_service.core.engine_sync import engine

router = APIRouter(prefix="/health", tags=["health"])


def _redis_status() -> tuple[bool, bool]:
    """Return (redis_ok, circuit_breaker_open)."""
    if not settings.requires_redis:
        return True, False
    ok = get_redis_client() is not None
    return ok, not ok


def _db_status() -> bool:
    """Return True when the database accepts a simple query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _degradation_modes() -> dict[str, str]:
    return {
        "rate_limit": settings.effective_failure_mode("rate_limit"),
        "refresh_validation": settings.effective_failure_mode("refresh_validation"),
        "session_write": settings.effective_failure_mode("session_write"),
        "access_revocation": settings.effective_failure_mode("access_revocation"),
    }


@router.get("/", summary="Service health and infrastructure status")
def health_check() -> dict[str, Any]:
    """Return effective operating state including Redis and database reachability.

    Useful for monitoring and for diagnosing silent degradation when TOKEN_MODE
    is ``stateful`` or ``hybrid`` but Redis is unavailable.
    """
    redis_ok, circuit_breaker_open = _redis_status()
    db_ok = _db_status()

    effective_mode = (
        "stateless_degraded"
        if settings.requires_redis and not redis_ok
        else settings.TOKEN_MODE
    )
    degraded_since = get_redis_degraded_since()

    return {
        "status": "ok" if (redis_ok and db_ok) else "degraded",
        "token_mode": settings.TOKEN_MODE,
        "effective_mode": effective_mode,
        "redis": "ok" if redis_ok else "unavailable",
        "circuit_breaker": "open" if circuit_breaker_open else "closed",
        "database": "ok" if db_ok else "unavailable",
        "revocation_available": redis_ok and settings.requires_redis,
        "rate_limiting_available": redis_ok and settings.requires_redis,
        "degraded_since": degraded_since.isoformat() if degraded_since else None,
        "degradation_modes": _degradation_modes(),
    }
