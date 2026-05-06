"""
Alembic environment configuration module.

This module provides the configuration for Alembic to run database
migrations in both offline and online modes. It sets up the logging,
database engine, and migration context.
"""
# pylint: disable=no-member
from logging.config import fileConfig
import sys
import os
# add your project to PYTHONPATH if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..")))

import auth_user_service.db_models

from auth_user_service.core.config import settings
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlmodel import SQLModel
from alembic import context


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# from auth_user_service.schemas.users import SQLModel  # noqa
 # noqa

target_metadata = SQLModel.metadata
VERSION_TABLE = config.get_main_option("version_table")
VERSION_LOCATIONS = [config.get_main_option("version_locations")]
# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """
    Retrieve the database URL.

    Returns:
        str: The SQLAlchemy database URI from the settings.
    """
    return str(settings.SQLALCHEMY_DATABASE_URI)


def include_object(object, name, type_, reflected, compare_to):
    """
    Only include tables (and other objects) that start with 'prefix_' or are the version table.
    """
    # Always include the version table
    if type_ == "table":
        if name == VERSION_TABLE:
            return True

        if not reflected:
            # This is a model-defined table → include it
            return True
        else:
            # This is an existing DB table not in metadata → exclude
            return False
    return True


def run_migrations_offline():
    """
    Run migrations in 'offline' mode.

    This configures the migration context with a URL rather than an Engine.
    This mode allows running migrations without a DBAPI. Calls to
    context.execute() emit the given string to the script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        version_table=VERSION_TABLE,
        version_locations=VERSION_LOCATIONS
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    Run migrations in 'online' mode.

    This mode creates an Engine and associates a connection with the
    migration context. It then runs the migrations within a transaction.
    """
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
            version_locations=VERSION_LOCATIONS
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
