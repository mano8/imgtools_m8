"""
Module for initializing the database.

This module sets up the SQLAlchemy engine and provides a function
to initialize the database with initial data, specifically creating a
default superuser if one does not already exist. It is expected that
database tables are created via Alembic migrations.
"""

import logging

from sqlmodel import Session, select

from auth_sdk_m8.schemas.base import AuthProviderType, RoleType
from auth_user_service.core.config import settings
from auth_user_service.db_models.users import User, UserCreate
from auth_user_service.services.users import UserController

logger = logging.getLogger(__name__)
# make sure all SQLModel models are imported (app.models)
# before initializing DB otherwise, SQLModel might fail
# to initialize relationships properly
# for more details:
# https://github.com/fastapi/full-stack-fastapi-template/issues/28


def initial_user_db(session: Session) -> None:
    """
    Initialize the database with the first superuser on first run only.

    On the first run (no superuser in the DB), creates one from
    FIRST_SUPERUSER / FIRST_SUPERUSER_PASSWORD. On all subsequent starts,
    returns immediately — the env vars are always required by config but
    are only acted upon once.

    Parameters:
        session (Session):
            The SQLModel database session used for executing queries.
    """
    existing = session.exec(
        select(User).where(User.is_superuser)
    ).first()
    if existing:
        logger.info("Superuser already exists — skipping initial seed.")
        return

    user_in = UserCreate(
        provider=AuthProviderType.PASSWORD,
        provider_user_id=None,
        email=settings.FIRST_SUPERUSER,
        password=settings.FIRST_SUPERUSER_PASSWORD.get_secret_value(),
        is_superuser=True,
        role=RoleType.SUPERADMIN,
    )
    UserController.create_user(session=session, user_create=user_in)
