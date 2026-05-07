"""Unit tests for core.deps dependency functions."""
import secrets
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from auth_user_service.core.deps import (
    get_current_active_superuser,
    get_current_user,
    get_redis_client,
    verify_private_api_secret,
)
from auth_user_service.core.security import SecurityHelper
from auth_sdk_m8.schemas.auth import TokenAccessData, TokenSecret
from auth_sdk_m8.schemas.user import UserModel


def _make_valid_token(user_id: str = None) -> str:
    """Create a signed access token that passes decode_access_token validation."""
    import re
    _pattern = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[-_])[A-Za-z\d\-_]{32,}$"
    )
    key = secrets.token_urlsafe(32)
    while not _pattern.match(key):
        key = secrets.token_urlsafe(32)

    from auth_user_service.core.config import settings
    data = TokenAccessData(
        sub=user_id or str(uuid.uuid4()),
        role="user",
        email="dep_test@example.com",
        full_name="Dep Test",
        is_superuser=False,
    )
    token_secret = TokenSecret(
        secret_key=settings.ACCESS_SECRET_KEY,
        algorithm=settings.TOKEN_ALGORITHM,
    )
    token, _ = SecurityHelper.create_access_token(
        data=data,
        expires_delta=timedelta(minutes=30),
        secrets=token_secret,
    )
    return token


class TestGetCurrentUser:
    def test_valid_token_not_revoked_returns_user_model(self):
        token = _make_valid_token()
        mock_redis = MagicMock()

        mock_redis_manager = MagicMock()
        mock_redis_manager.is_blacklisted.return_value = False

        with patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls:
            mock_cls.return_value = mock_redis_manager
            result = get_current_user(token=token, redis=mock_redis)

        assert isinstance(result, UserModel)
        assert result.email == "dep_test@example.com"

    def test_revoked_session_raises_401(self):
        token = _make_valid_token()
        mock_redis = MagicMock()

        mock_redis_manager = MagicMock()
        mock_redis_manager.is_blacklisted.return_value = True

        with patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls:
            mock_cls.return_value = mock_redis_manager
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token, redis=mock_redis)

        assert exc_info.value.status_code == 401

    def test_invalid_token_raises_403(self):
        mock_redis = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="this.is.not.a.valid.jwt", redis=mock_redis)

        assert exc_info.value.status_code == 403

    def test_inactive_user_raises_403(self):
        from auth_user_service.core.config import settings
        data = TokenAccessData(
            sub=str(uuid.uuid4()),
            role="user",
            email="inactive@example.com",
            full_name="Inactive",
            is_superuser=False,
            is_active=False,
        )
        token_secret = TokenSecret(
            secret_key=settings.ACCESS_SECRET_KEY,
            algorithm=settings.TOKEN_ALGORITHM,
        )
        token, _ = SecurityHelper.create_access_token(
            data=data,
            expires_delta=timedelta(minutes=30),
            secrets=token_secret,
        )

        mock_redis = MagicMock()
        mock_redis_manager = MagicMock()
        mock_redis_manager.is_blacklisted.return_value = False

        with patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls:
            mock_cls.return_value = mock_redis_manager
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token, redis=mock_redis)

        assert exc_info.value.status_code == 403


class TestGetCurrentActiveSuperuser:
    def test_superuser_passes_through(self):
        user = MagicMock(spec=UserModel)
        user.is_superuser = True

        result = get_current_active_superuser(current_user=user)

        assert result is user

    def test_non_superuser_raises_403(self):
        user = MagicMock(spec=UserModel)
        user.is_superuser = False

        with pytest.raises(HTTPException) as exc_info:
            get_current_active_superuser(current_user=user)

        assert exc_info.value.status_code == 403


class TestGetTemplates:
    def test_returns_jinja2_templates(self):
        from auth_user_service.core.deps import get_templates

        with patch("auth_user_service.core.deps.Jinja2Templates") as mock_jinja:
            mock_instance = MagicMock()
            mock_jinja.return_value = mock_instance

            result = get_templates()

        assert result is mock_instance
        mock_jinja.assert_called_once()


class TestGetRedisClient:
    def test_returns_redis_instance(self):
        from redis import Redis
        client = get_redis_client()
        assert isinstance(client, Redis)


class TestVerifyPrivateApiSecret:
    def test_correct_secret_passes(self):
        from auth_user_service.core.config import settings
        correct = settings.PRIVATE_API_SECRET.get_secret_value()
        verify_private_api_secret(x_internal_token=correct)  # should not raise

    def test_wrong_secret_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_private_api_secret(x_internal_token="completely_wrong_secret")

        assert exc_info.value.status_code == 401
