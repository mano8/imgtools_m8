"""
dm_model's helpers
"""

from fastapi_service.core.config import settings


def prefixed_tables(name: str) -> str:
    """Return a table name prefixed with the configured TABLES_PREFIX."""
    return f"{settings.TABLES_PREFIX}_{name}"
