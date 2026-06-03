"""
Main routes
"""

from fastapi import APIRouter

from fastapi_full.app.routes import dashboard, category

api_router = APIRouter()
api_router.include_router(dashboard.router)
api_router.include_router(category.router)
