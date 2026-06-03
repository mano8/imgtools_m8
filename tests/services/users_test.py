"""Unit tests for services.users.UserController."""

import uuid

import pytest

from auth_user_service.db_models.users import UserCreate, UserUpdate
from auth_user_service.services.users import UserController
from auth_sdk_m8.schemas.base import AuthProviderType


class TestCreateUser:
    def test_password_provider_hashes_password(self, db_session):
        user_create = UserCreate(
            email=f"newuser_{uuid.uuid4().hex[:6]}@example.com",
            password="securepassword",
            provider=AuthProviderType.PASSWORD,
        )

        user = UserController.create_user(session=db_session, user_create=user_create)

        assert user.id is not None
        assert user.hashed_password is not None
        assert user.hashed_password != "securepassword"
        assert user.email == user_create.email

    def test_password_provider_sets_uuid_id(self, db_session):
        user_create = UserCreate(
            email=f"uid_{uuid.uuid4().hex[:6]}@example.com",
            password="securepassword",
            provider=AuthProviderType.PASSWORD,
        )

        user = UserController.create_user(session=db_session, user_create=user_create)

        assert user.id is not None
        uuid.UUID(str(user.id))  # validates it is a UUID

    def test_google_provider_creates_without_password(self, db_session):
        user_create = UserCreate(
            email=f"google_{uuid.uuid4().hex[:6]}@example.com",
            oauth_user_id=f"gid_{uuid.uuid4().hex}",
            provider=AuthProviderType.GOOGLE,
        )

        user = UserController.create_user(session=db_session, user_create=user_create)

        assert user.id is not None
        assert user.hashed_password is None
        assert user.oauth_user_id == user_create.oauth_user_id

    def test_password_provider_missing_password_raises(self, db_session):
        bad_create = UserCreate.model_construct(
            email=f"bad_{uuid.uuid4().hex[:6]}@example.com",
            password=None,
            provider=AuthProviderType.PASSWORD,
        )
        with pytest.raises(ValueError, match="password is required"):
            UserController.create_user(session=db_session, user_create=bad_create)


class TestUpdateUser:
    def test_update_full_name(self, db_session, sample_user):
        update = UserUpdate(full_name="New Name")

        updated = UserController.update_user(
            session=db_session,
            db_user=sample_user,
            user_in=update,
        )

        assert updated.full_name == "New Name"

    def test_update_password_rehashes(self, db_session, sample_user):
        old_hash = sample_user.hashed_password
        update = UserUpdate(
            provider=AuthProviderType.PASSWORD,
            password="newpassword123",
        )

        updated = UserController.update_user(
            session=db_session,
            db_user=sample_user,
            user_in=update,
        )

        assert updated.hashed_password != old_hash

    def test_update_without_password_preserves_hash(self, db_session, sample_user):
        old_hash = sample_user.hashed_password
        update = UserUpdate(full_name="Only Name Update")

        updated = UserController.update_user(
            session=db_session,
            db_user=sample_user,
            user_in=update,
        )

        assert updated.hashed_password == old_hash


class TestGetUser:
    def test_returns_user_by_id(self, db_session, sample_user):
        result = UserController.get_user(session=db_session, user_id=sample_user.id)

        assert result is not None
        assert str(result.id) == str(sample_user.id)

    def test_returns_none_for_unknown_id(self, db_session):
        result = UserController.get_user(session=db_session, user_id=uuid.uuid4())

        assert result is None


class TestGetUserByEmail:
    def test_returns_user_by_email(self, db_session, sample_user):
        result = UserController.get_user_by_email(
            session=db_session, email=sample_user.email
        )

        assert result is not None
        assert result.email == sample_user.email

    def test_returns_none_for_unknown_email(self, db_session):
        result = UserController.get_user_by_email(
            session=db_session, email="nobody@nowhere.com"
        )

        assert result is None


class TestCountUsers:
    def test_count_increases_after_create(self, db_session):
        before = UserController.count_users(session=db_session)

        user_create = UserCreate(
            email=f"count_{uuid.uuid4().hex[:6]}@example.com",
            password="password123",
            provider=AuthProviderType.PASSWORD,
        )
        UserController.create_user(session=db_session, user_create=user_create)

        after = UserController.count_users(session=db_session)
        assert after == before + 1

    def test_count_returns_integer(self, db_session):
        result = UserController.count_users(session=db_session)
        assert isinstance(result, int)
        assert result >= 0
