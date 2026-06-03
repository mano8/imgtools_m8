from fastapi import APIRouter

from auth_user_service.routes import (
    api_keys,
    dashboard,
    google_auth,
    health,
    jwks,
    login,
    oauth_login,
    private,
    profile,
    sessions,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(jwks.router)
api_router.include_router(profile.router)
api_router.include_router(api_keys.router)
api_router.include_router(users.router)
api_router.include_router(login.router)
api_router.include_router(oauth_login.router)
api_router.include_router(google_auth.router)
api_router.include_router(sessions.router)
api_router.include_router(dashboard.router)
api_router.include_router(private.router)
