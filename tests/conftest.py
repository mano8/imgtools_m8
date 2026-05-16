"""
Shared pytest fixtures for the fa-auth-m8 test suite.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# SQLite does not natively support uuid.UUID — register an adapter so that
# SQLAlchemy can bind UUID values when using the in-memory test engine.
sqlite3.register_adapter(uuid.UUID, str)
sqlite3.register_converter("CHAR", lambda b: b.decode("utf-8"))

from auth_user_service.core.security import SecurityHelper  # noqa: E402
from auth_user_service.db_models.api_keys import ApiKey, RateLimit  # noqa: E402, F401
from auth_user_service.db_models.sessions import ClientSession  # noqa: E402
from auth_user_service.db_models.users import User  # noqa: E402
from auth_sdk_m8.schemas.base import AuthProviderType, RoleType  # noqa: E402

TEST_PASSWORD = "testpassword123"


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
            "detect_types": sqlite3.PARSE_DECLTYPES,
        },
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def sample_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"user_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test User",
        hashed_password=SecurityHelper.get_password_hash(TEST_PASSWORD),
        provider=AuthProviderType.PASSWORD,
        is_active=True,
        email_verified=True,
        is_superuser=False,
        role=RoleType.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"inactive_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Inactive User",
        hashed_password=SecurityHelper.get_password_hash(TEST_PASSWORD),
        provider=AuthProviderType.PASSWORD,
        is_active=False,
        email_verified=False,
        is_superuser=False,
        role=RoleType.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def superuser(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"superuser_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Super User",
        hashed_password=SecurityHelper.get_password_hash(TEST_PASSWORD),
        provider=AuthProviderType.PASSWORD,
        is_active=True,
        email_verified=True,
        is_superuser=True,
        role=RoleType.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def google_user(db_session):
    user = User(
        id=uuid.uuid4(),
        email=f"google_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Google User",
        oauth_user_id=f"google_{uuid.uuid4().hex}",
        provider=AuthProviderType.GOOGLE,
        is_active=True,
        email_verified=True,
        is_superuser=False,
        role=RoleType.USER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_client_session(db_session, sample_user):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    client_session = ClientSession(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        provider=AuthProviderType.PASSWORD,
        jwt_jti=str(uuid.uuid4()),
        refresh_token_hash="a" * 64,
        jwt_expires_at=now + timedelta(hours=1),
        refresh_expires_at=now + timedelta(days=7),
        revoked=False,
    )
    db_session.add(client_session)
    db_session.commit()
    db_session.refresh(client_session)
    return client_session


@pytest.fixture
def expired_client_session(db_session, sample_user):
    past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
    client_session = ClientSession(
        id=str(uuid.uuid4()),
        user_id=sample_user.id,
        provider=AuthProviderType.PASSWORD,
        jwt_jti=str(uuid.uuid4()),
        refresh_token_hash="b" * 64,
        jwt_expires_at=past,
        refresh_expires_at=past,
        revoked=False,
    )
    db_session.add(client_session)
    db_session.commit()
    db_session.refresh(client_session)
    return client_session


_UNIT_DIRS = {"core", "services", "schemas", "db_models", "utils"}


def pytest_collection_modifyitems(config, items: list) -> None:
    for item in items:
        if item.fspath.dirpath().basename in _UNIT_DIRS:
            item.add_marker(pytest.mark.unit)
