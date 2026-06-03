"""Minimal fastapi-m8 consumer service.

Bootstraps the entire app in a few lines:

1. Import settings, auth deps, and the domain router.
2. Call ``create_app`` — CORS, health endpoint, lifespan are wired automatically.
3. Point uvicorn at ``app``.
"""

from fastapi import APIRouter

from fastapi_m8 import AppLifecycle, create_app

from .core.config import settings
from .core.deps import auth
from .routes import router as hello_router

api_router = APIRouter(prefix=settings.API_PREFIX)
api_router.include_router(hello_router)

app = create_app(
    settings,
    api_router,
    service_name="example-minimal",
    service_version="1.0.0",
    lifecycle=AppLifecycle(auth_deps=auth),
)
