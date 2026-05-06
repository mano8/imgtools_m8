"""
dm_model's helpers
"""
from sqlmodel import SQLModel
from sqlalchemy.ext.declarative import declared_attr
from fastapi_service.core.config import settings


class PrefixedBase(SQLModel):
    """
    Automatiquelly prefix table names.
    """
    @declared_attr
    @classmethod
    def __tablename__(cls) -> str:
        return f"{settings.TABLES_PREFIX}_{cls.__name__.lower()}"


def prefixed_fk(model: type, column: str) -> str:
    """
    Build a ForeignKey string like "prefix_model.column" dynamically,
    so it always matches model.__tablename__.
    """
    return f"{settings.TABLES_PREFIX}_{model}.{column}"


def prefixed_tables(name: str) -> str:
    """
    Build a ForeignKey string like "prefix_model.column" dynamically,
    so it always matches model.__tablename__.
    """
    return f"{settings.TABLES_PREFIX}_{name}"
