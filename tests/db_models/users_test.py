"""Unit tests for db_models.users validation logic."""

import uuid

import pytest

from auth_user_service.db_models.users import (
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdate,
    UserUpdateMe,
    UsersPublic,
)
from auth_sdk_m8.schemas.base import AuthProviderType, RoleType


class TestUserCreate:
    def test_password_provider_valid(self):
        user = UserCreate(
            email="user@example.com",
            password="securepass123",
            provider=AuthProviderType.PASSWORD,
        )
        assert user.email == "user@example.com"
        assert user.password == "securepass123"

    def test_google_provider_valid(self):
        user = UserCreate(
            email="guser@example.com",
            oauth_user_id="google_uid_123",
            provider=AuthProviderType.GOOGLE,
        )
        assert user.oauth_user_id == "google_uid_123"
        assert user.password is None

    def test_password_provider_missing_password_raises(self):
        with pytest.raises(Exception):
            UserCreate(
                email="user@example.com",
                provider=AuthProviderType.PASSWORD,
                # password omitted → defaults to None
            )

    def test_password_provider_with_oauth_id_raises(self):
        with pytest.raises(Exception):
            UserCreate(
                email="user@example.com",
                password="securepass123",
                oauth_user_id="some_id",
                provider=AuthProviderType.PASSWORD,
            )

    def test_google_provider_missing_oauth_id_raises(self):
        with pytest.raises(Exception):
            UserCreate(
                email="user@example.com",
                provider=AuthProviderType.GOOGLE,
                # oauth_user_id omitted
            )

    def test_google_provider_with_password_raises(self):
        with pytest.raises(Exception):
            UserCreate(
                email="user@example.com",
                oauth_user_id="google_uid",
                password="somepass123",
                provider=AuthProviderType.GOOGLE,
            )

    def test_default_role_is_user(self):
        user = UserCreate(
            email="user@example.com",
            password="securepass123",
            provider=AuthProviderType.PASSWORD,
        )
        assert user.role == RoleType.USER

    def test_default_is_active_true(self):
        user = UserCreate(
            email="user@example.com",
            password="securepass123",
            provider=AuthProviderType.PASSWORD,
        )
        assert user.is_active is True


class TestUserUpdate:
    def test_valid_password_provider_update(self):
        update = UserUpdate(
            full_name="New Name",
            provider=AuthProviderType.PASSWORD,
        )
        assert update.full_name == "New Name"

    def test_valid_google_provider_update(self):
        update = UserUpdate(
            full_name="Google Name",
            provider=AuthProviderType.GOOGLE,
        )
        assert update.full_name == "Google Name"

    def test_password_provider_with_oauth_id_raises(self):
        with pytest.raises(Exception):
            UserUpdate(
                provider=AuthProviderType.PASSWORD,
                oauth_user_id="should_not_be_here",
            )

    def test_google_provider_with_password_raises(self):
        with pytest.raises(Exception):
            UserUpdate(
                provider=AuthProviderType.GOOGLE,
                password="shouldnotallow",
            )

    def test_no_provider_allows_all_optional_fields(self):
        update = UserUpdate(
            full_name="Name",
            email="new@example.com",
        )
        assert update.full_name == "Name"


class TestUserRegister:
    def test_valid_registration(self):
        reg = UserRegister(
            email="reg@example.com",
            password="registerpass",
            full_name="Register User",
        )
        assert reg.email == "reg@example.com"
        assert reg.full_name == "Register User"

    def test_full_name_optional(self):
        reg = UserRegister(
            email="reg@example.com",
            password="registerpass",
        )
        assert reg.full_name is None


class TestUserUpdateMe:
    def test_all_fields_optional(self):
        update = UserUpdateMe()
        assert update.email is None
        assert update.full_name is None
        assert update.avatar is None

    def test_partial_update(self):
        update = UserUpdateMe(full_name="Me Updated")
        assert update.full_name == "Me Updated"


class TestUpdatePassword:
    def test_valid_passwords(self):
        p = UpdatePassword(
            current_password="oldpassword",
            new_password="newpassword",
        )
        assert p.current_password == "oldpassword"
        assert p.new_password == "newpassword"


class TestUserPublicAndList:
    def test_users_public_wrapper(self):
        pub_user = UserPublic(
            id=uuid.uuid4(),
            email="pub@example.com",
            provider=AuthProviderType.PASSWORD,
            is_active=True,
            email_verified=False,
            is_superuser=False,
            role=RoleType.USER,
        )
        users_pub = UsersPublic(data=[pub_user], count=1)

        assert users_pub.count == 1
        assert len(users_pub.data) == 1
