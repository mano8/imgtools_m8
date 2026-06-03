"""fastapi_full — full-featured fastapi-m8 consumer service.

Demonstrates: DB session, metrics, health checks, auth deps, lifespan teardown.
All wiring is handled by ``create_app``; this file only imports and connects.
"""

from fastapi import APIRouter

from fastapi_m8 import create_app

from .app.main import api_router as domain_router
from .core.config import settings
from .core.deps import auth, engine

api_router = APIRouter(prefix=settings.API_PREFIX)
api_router.include_router(domain_router)

app = create_app(
    settings,
    api_router,
    service_name=settings.PROJECT_NAME,
    service_version="1.0.0",
    auth_deps=auth,
    db_engine=engine,
)
