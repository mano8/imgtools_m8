"""Tests for schemas.user and schemas.google."""

import uuid

from auth_user_service.schemas.user import (
    OAuthGoogleToken,
    ResponseUser,
)
from auth_user_service.db_models.users import UserPublic
from auth_sdk_m8.schemas.base import AuthProviderType, RoleType


class TestOAuthGoogleTokenSchema:
    def test_valid_schema(self):
        token = OAuthGoogleToken(
            access_token="acc_token",
            expires_in=3600,
            refresh_token="ref_token",
        )
        assert token.access_token == "acc_token"
        assert token.expires_in == 3600
        assert token.refresh_token == "ref_token"


class TestResponseUser:
    def test_valid_response(self):
        pub_user = UserPublic(
            id=uuid.uuid4(),
            email="user@example.com",
            provider=AuthProviderType.PASSWORD,
            is_active=True,
            email_verified=True,
            is_superuser=False,
            role=RoleType.USER,
        )
        resp = ResponseUser(success=True, user=pub_user)

        assert resp.success is True
        assert resp.user.email == "user@example.com"
