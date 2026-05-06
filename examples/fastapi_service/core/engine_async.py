"""Initialise the database connection."""
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi_service.core.config import settings

async_engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=True,
    future=True
)
