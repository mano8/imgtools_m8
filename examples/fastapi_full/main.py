"""fastapi_full — full-featured fastapi-m8 consumer service.

Demonstrates: DB session, metrics, health checks, auth deps, lifespan teardown.
All wiring is handled by ``create_app``; this file only imports and connects.
"""

from fastapi import APIRouter
from sqlmodel import select

from fastapi_m8 import (
    AppLifecycle,
    HealthCheckResult,
    HealthConfig,
    HealthStatus,
    create_app,
)

from .app.main import api_router as domain_router
from .core.config import settings
from .core.deps import auth, engine


async def check_db() -> HealthCheckResult:
    """Check database reachability."""
    try:
        with engine.session() as s:
            s.exec(select(1))
        return HealthCheckResult.from_bool("database", True)
    except Exception as exc:
        return HealthCheckResult(name="database", status=HealthStatus.FAIL, error=str(exc))


api_router = APIRouter(prefix=settings.API_PREFIX)
api_router.include_router(domain_router)

app = create_app(
    settings,
    api_router,
    service_name=settings.PROJECT_NAME,
    service_version="1.0.0",
    health=HealthConfig(checks=[check_db]),
    lifecycle=AppLifecycle(auth_deps=auth, db_engine=engine),
)
