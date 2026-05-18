"""Unit tests for core.deps dependency functions."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from auth_user_service.core.client import RateLimitResult
from auth_user_service.core.deps import (
    get_current_active_superuser,
    get_current_api_key,
    get_current_user,
    get_redis_client,
    get_redis_degraded_since,
    verify_private_api_secret,
)
from auth_user_service.core.security import SecurityHelper
from auth_sdk_m8.schemas.auth import TokenAccessData, TokenSecret
from auth_sdk_m8.schemas.base import Period
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
        algorithm=settings.ACCESS_TOKEN_ALGORITHM,
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

        with (
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=mock_redis
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls,
        ):
            mock_cls.return_value.is_blacklisted.return_value = False
            result = get_current_user(token=token)

        assert isinstance(result, UserModel)
        assert result.email == "dep_test@example.com"

    def test_revoked_session_raises_401(self):
        token = _make_valid_token()
        mock_redis = MagicMock()

        with (
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=mock_redis
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls,
        ):
            mock_cls.return_value.is_blacklisted.return_value = True
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token)

        assert exc_info.value.status_code == 401

    def test_invalid_token_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="this.is.not.a.valid.jwt")

        assert exc_info.value.status_code == 403

    def test_non_stateful_mode_skips_blacklist_check(self):
        token = _make_valid_token()

        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client") as mock_get_redis,
        ):
            mock_cfg.TOKEN_MODE = "hybrid"
            mock_cfg.is_stateful = False
            result = get_current_user(token=token)

        mock_get_redis.assert_not_called()
        assert isinstance(result, UserModel)

    def test_redis_unavailable_fail_closed_access_revocation_raises_503(self):
        """Redis down + ACCESS_REVOCATION_FAILURE_MODE=fail_closed must return 503."""
        token = _make_valid_token()

        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client", return_value=None),
        ):
            mock_cfg.is_stateful = True
            mock_cfg.effective_failure_mode.return_value = "fail_closed"
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token)

        assert exc_info.value.status_code == 503

    def test_redis_unavailable_fail_open_access_revocation_proceeds(self):
        """Redis down + ACCESS_REVOCATION_FAILURE_MODE=fail_open must allow through."""
        token = _make_valid_token()

        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client", return_value=None),
        ):
            mock_cfg.is_stateful = True
            mock_cfg.effective_failure_mode.return_value = "fail_open"
            mock_cfg.is_active = True
            result = get_current_user(token=token)

        assert isinstance(result, UserModel)

    def test_redis_unavailable_emits_degraded_decision_counter(self):
        """Redis down path increments degraded_decision_total with correct labels."""
        token = _make_valid_token()
        mock_metrics = MagicMock()
        mock_metrics.degraded_decision_total = MagicMock()

        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client", return_value=None),
            patch("auth_user_service.core.deps._get_metrics", return_value=mock_metrics),
        ):
            mock_cfg.is_stateful = True
            mock_cfg.effective_failure_mode.return_value = "fail_open"
            mock_cfg.is_active = True
            get_current_user(token=token)

        mock_metrics.degraded_decision_total.labels.assert_called_once_with(
            control="access_revocation", mode="fail_open", reason="redis_unavailable"
        )
        mock_metrics.degraded_decision_total.labels.return_value.inc.assert_called_once()

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
            algorithm=settings.ACCESS_TOKEN_ALGORITHM,
        )
        token, _ = SecurityHelper.create_access_token(
            data=data,
            expires_delta=timedelta(minutes=30),
            secrets=token_secret,
        )

        mock_redis = MagicMock()
        with (
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=mock_redis
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls,
        ):
            mock_cls.return_value.is_blacklisted.return_value = False
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token)

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
    def test_returns_redis_instance_when_ping_succeeds(self):
        from redis import Redis

        mock_client = MagicMock(spec=Redis)
        mock_client.ping.return_value = True
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
        ):
            client = get_redis_client()
        assert client is mock_client

    def test_returns_none_when_pool_is_none(self):
        with patch("auth_user_service.core.deps._redis_pool", None):
            result = get_redis_client()
        assert result is None

    def test_returns_none_when_ping_fails(self):
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("refused")
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
        ):
            result = get_redis_client()
        assert result is None


class TestVerifyPrivateApiSecret:
    def test_correct_secret_passes(self):
        from auth_user_service.core.config import settings

        correct = settings.PRIVATE_API_SECRET.get_secret_value()
        verify_private_api_secret(x_internal_token=correct)  # should not raise

    def test_wrong_secret_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            verify_private_api_secret(x_internal_token="completely_wrong_secret")

        assert exc_info.value.status_code == 401


class TestGetRedisDegradedSince:
    def test_returns_none_initially(self):
        with patch("auth_user_service.core.deps._redis_degraded_since", None):
            result = get_redis_degraded_since()
        assert result is None

    def test_returns_datetime_when_degraded(self):
        ts = datetime.now(timezone.utc)
        with patch("auth_user_service.core.deps._redis_degraded_since", ts):
            result = get_redis_degraded_since()
        assert result == ts


class TestGetCurrentUserMetrics:
    """Cover the Prometheus metric-emit branches inside get_current_user."""

    def _mock_metrics(self):
        m = MagicMock()
        m.token_validation_failures_total = MagicMock()
        return m

    def test_invalid_token_emits_invalid_metric(self):
        mock_m = self._mock_metrics()
        with (
            patch("auth_user_service.core.deps._get_metrics", return_value=mock_m),
            pytest.raises(HTTPException),
        ):
            get_current_user(token="not.a.valid.jwt")

        mock_m.token_validation_failures_total.labels.assert_called_once_with(
            reason="invalid"
        )

    def test_revoked_token_emits_revoked_metric(self):
        token = _make_valid_token()
        mock_m = self._mock_metrics()

        with (
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=MagicMock()
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls,
            patch("auth_user_service.core.deps._get_metrics", return_value=mock_m),
            pytest.raises(HTTPException) as exc_info,
        ):
            mock_cls.return_value.is_blacklisted.return_value = True
            get_current_user(token=token)

        assert exc_info.value.status_code == 401
        mock_m.token_validation_failures_total.labels.assert_called_once_with(
            reason="revoked"
        )

    def test_inactive_user_emits_inactive_metric(self):
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
            algorithm=settings.ACCESS_TOKEN_ALGORITHM,
        )
        token, _ = SecurityHelper.create_access_token(
            data=data,
            expires_delta=timedelta(minutes=30),
            secrets=token_secret,
        )

        mock_m = self._mock_metrics()
        with (
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=MagicMock()
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_cls,
            patch("auth_user_service.core.deps._get_metrics", return_value=mock_m),
            pytest.raises(HTTPException) as exc_info,
        ):
            mock_cls.return_value.is_blacklisted.return_value = False
            get_current_user(token=token)

        assert exc_info.value.status_code == 403
        mock_m.token_validation_failures_total.labels.assert_called_once_with(
            reason="inactive"
        )


class TestGetCurrentApiKey:
    """Cover all branches of the get_current_api_key dependency."""

    def _make_api_key(self):
        api_key = MagicMock()
        api_key.id = uuid.uuid4()
        api_key.user_id = uuid.uuid4()
        return api_key

    def _make_response(self):
        resp = MagicMock()
        resp.headers = {}
        return resp

    def test_invalid_key_raises_401(self, db_session):
        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=None,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            get_current_api_key(
                session=db_session,
                redis=None,
                response=self._make_response(),
                x_api_key="ak_bad",
            )

        assert exc_info.value.status_code == 401

    def test_no_redis_strict_mode_raises_503(self, db_session):
        api_key = self._make_api_key()

        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=api_key,
            ),
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            pytest.raises(HTTPException) as exc_info,
        ):
            mock_cfg.API_KEY_STRICT_RATE_LIMIT = True
            get_current_api_key(
                session=db_session,
                redis=None,
                response=self._make_response(),
                x_api_key="ak_valid",
            )

        assert exc_info.value.status_code == 503

    def test_no_redis_non_strict_returns_key(self, db_session):
        api_key = self._make_api_key()

        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=api_key,
            ),
            patch("auth_user_service.core.deps.settings") as mock_cfg,
        ):
            mock_cfg.API_KEY_STRICT_RATE_LIMIT = False
            result = get_current_api_key(
                session=db_session,
                redis=None,
                response=self._make_response(),
                x_api_key="ak_valid",
            )

        assert result is api_key

    def test_redis_rate_limited_with_reset_at_raises_429(self, db_session):
        api_key = self._make_api_key()
        reset = datetime.now(timezone.utc) + timedelta(minutes=1)
        rate_result = RateLimitResult(
            allowed=False,
            exceeded_period=Period.MINUTE,
            reset_at=reset,
        )

        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=api_key,
            ),
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_limits",
                return_value=[],
            ),
            patch("auth_user_service.core.deps.RateLimitEnforcer") as mock_enforcer_cls,
            pytest.raises(HTTPException) as exc_info,
        ):
            mock_enforcer_cls.return_value.enforce.return_value = rate_result
            get_current_api_key(
                session=db_session,
                redis=MagicMock(),
                response=self._make_response(),
                x_api_key="ak_valid",
            )

        assert exc_info.value.status_code == 429

    def test_redis_rate_limited_no_reset_at_defaults_retry_after_60(self, db_session):
        api_key = self._make_api_key()
        rate_result = RateLimitResult(
            allowed=False,
            exceeded_period=Period.HOUR,
            reset_at=None,
        )

        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=api_key,
            ),
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_limits",
                return_value=[],
            ),
            patch("auth_user_service.core.deps.RateLimitEnforcer") as mock_enforcer_cls,
            pytest.raises(HTTPException) as exc_info,
        ):
            mock_enforcer_cls.return_value.enforce.return_value = rate_result
            get_current_api_key(
                session=db_session,
                redis=MagicMock(),
                response=self._make_response(),
                x_api_key="ak_valid",
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.headers["Retry-After"] == "60"

    def test_redis_allowed_sets_headers_and_returns_key(self, db_session):
        api_key = self._make_api_key()
        reset = datetime.now(timezone.utc) + timedelta(minutes=1)
        rate_result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=50,
            reset_at=reset,
        )
        mock_redis = MagicMock()
        response = self._make_response()

        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=api_key,
            ),
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_limits",
                return_value=[],
            ),
            patch("auth_user_service.core.deps.RateLimitEnforcer") as mock_enforcer_cls,
        ):
            mock_enforcer_cls.return_value.enforce.return_value = rate_result
            result = get_current_api_key(
                session=db_session,
                redis=mock_redis,
                response=response,
                x_api_key="ak_valid",
            )

        assert result is api_key
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_redis_allowed_no_header_fields_and_hset_failure_still_returns(
        self, db_session
    ):
        api_key = self._make_api_key()
        rate_result = RateLimitResult(
            allowed=True,
            limit=None,
            remaining=None,
            reset_at=None,
        )
        mock_redis = MagicMock()
        mock_redis.hset.side_effect = Exception("redis down")

        with (
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_active_key",
                return_value=api_key,
            ),
            patch(
                "auth_user_service.core.deps.ApiKeyService.get_limits",
                return_value=[],
            ),
            patch("auth_user_service.core.deps.RateLimitEnforcer") as mock_enforcer_cls,
        ):
            mock_enforcer_cls.return_value.enforce.return_value = rate_result
            result = get_current_api_key(
                session=db_session,
                redis=mock_redis,
                response=self._make_response(),
                x_api_key="ak_valid",
            )

        assert result is api_key
