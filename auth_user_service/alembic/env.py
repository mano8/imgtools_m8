"""
Alembic environment configuration module.

Handles database migrations in offline and online modes.
"""
# pylint: disable=invalid-name,too-many-arguments,too-few-public-methods
# pylint: disable=unused-import,consider-using-f-string,no-member
# pylint: disable=redefined-builtin,unused-argument

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from auth_user_service.core.config import settings

import auth_user_service.db_models  # noqa: F401


# ---------------------------------------------------------------------
# PYTHONPATH (Docker / monorepo safe)
# ---------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


# ---------------------------------------------------------------------
# ALEMBIC CONFIG
# ---------------------------------------------------------------------
config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

VERSION_TABLE = config.get_main_option("version_table")
VERSION_LOCATIONS = [config.get_main_option("version_locations")]


# ---------------------------------------------------------------------
# DATABASE URL
# ---------------------------------------------------------------------
def get_url() -> str:
    """Return SQLAlchemy database URL from settings."""
    return str(settings.SQLALCHEMY_DATABASE_URI)


# ---------------------------------------------------------------------
# INCLUDE OBJECT FILTER
# ---------------------------------------------------------------------
def include_object(
    object,  # noqa: A002
    name: str,
    type_: str,
    reflected: bool,
    compare_to: object,
) -> bool:
    """
    Filter database objects included in migrations.
    """
    if type_ == "table":
        if name == VERSION_TABLE:
            return True
        return not reflected

    return True


# ---------------------------------------------------------------------
# OFFLINE MIGRATIONS
# ---------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        version_table=VERSION_TABLE,
        version_locations=VERSION_LOCATIONS,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------
# ONLINE MIGRATIONS
# ---------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in online mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
            version_table=VERSION_TABLE,
            version_locations=VERSION_LOCATIONS,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
