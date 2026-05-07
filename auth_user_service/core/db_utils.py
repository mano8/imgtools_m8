"""
dm_model's helpers
"""
import uuid
from typing import Any, Dict, Optional
from sqlmodel import SQLModel
from sqlalchemy import types
from sqlalchemy.ext.declarative import declared_attr
from auth_user_service.core.config import settings


class UUIDChar(types.TypeDecorator):
    """
    Store UUIDs as CHAR(36) strings.

    Coerces uuid.UUID → str on bind so PostgreSQL's strict type system
    compares character(36) against a text literal (not the uuid wire type
    that psycopg2 would otherwise send).  Converts back to uuid.UUID on read.
    Works identically on MySQL.
    """

    impl = types.CHAR(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if isinstance(value, uuid.UUID):
            return str(value)
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Optional[uuid.UUID]:
        if value is None:
            return None
        return uuid.UUID(str(value))


def get_table_args() -> Dict[str, Any]:
    """Return engine-specific table args for the selected database."""
    if settings.SELECTED_DB == "Mysql":
        return {"mysql_engine": settings.DB_ENGINE, "mysql_charset": settings.DB_CHARSET}
    return {}


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
