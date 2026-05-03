"""Tests for schemas.user and schemas.google."""
import uuid
import pytest

from auth_user_service.schemas.user import OAuthGoogleToken, ResponseUploadedAvatar, ResponseUser
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


class TestResponseUploadedAvatar:
    def test_valid_response(self):
        resp = ResponseUploadedAvatar(
            success=True,
            msg="Avatar uploaded",
            avatar="https://example.com/avatar.png",
        )
        assert resp.success is True
        assert resp.msg == "Avatar uploaded"
        assert resp.avatar == "https://example.com/avatar.png"

    def test_failure_response(self):
        resp = ResponseUploadedAvatar(
            success=False,
            msg="Upload failed",
            avatar="",
        )
        assert resp.success is False


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
