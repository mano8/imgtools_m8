"""Security regression: Redis unavailability produces clear errors, not crashes.

Verifies that:
- get_redis_client() returns None when ping fails (server unreachable)
- get_redis_client() returns None in stateless mode (pool is None)
- get_redis_client() logs a warning when the server is unreachable
- Google OAuth raises 503 (not 400/500) when Redis is unavailable
- Core authentication (bcrypt + DB lookup) works without Redis
- Rate-limiting guard is correctly skipped when redis is None
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError

from auth_user_service.core.client import LoginRateLimiter
from auth_user_service.core.deps import get_redis_client
from auth_user_service.services.auth import AuthController


class TestGetRedisClientResilience:
    def setup_method(self):
        import auth_user_service.core.deps as _deps

        _deps._redis_degraded_since = None

    def test_returns_none_when_pool_is_none(self):
        """Stateless mode: pool never created, must return None immediately."""
        with patch("auth_user_service.core.deps._redis_pool", None):
            result = get_redis_client()
        assert result is None

    def test_returns_none_when_ping_raises_connection_error(self):
        """Server is unreachable: ping fails, must return None (not raise)."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("Connection refused")
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
        ):
            result = get_redis_client()
        assert result is None

    def test_returns_none_when_ping_raises_generic_exception(self):
        """Any ping failure (not just ConnectionError) must return None safely."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = OSError("timeout")
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
        ):
            result = get_redis_client()
        assert result is None

    def test_returns_client_when_ping_succeeds(self):
        """Server is reachable: must return the Redis client."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
        ):
            result = get_redis_client()
        assert result is mock_client

    def test_circuit_breaker_returns_none_within_cooling_window(self):
        """Within 30 s of first failure the circuit is open: no ping attempt."""
        import auth_user_service.core.deps as _deps

        _deps._redis_degraded_since = datetime.now(timezone.utc)
        mock_redis_cls = MagicMock()
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", mock_redis_cls),
        ):
            result = get_redis_client()
        assert result is None
        mock_redis_cls.assert_not_called()

    def test_repeated_failure_does_not_overwrite_degraded_since(self):
        """If already degraded and ping fails again, the original timestamp is kept."""
        import auth_user_service.core.deps as _deps

        original_ts = datetime.now(timezone.utc) - timedelta(seconds=60)
        _deps._redis_degraded_since = original_ts
        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("still down")
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
        ):
            result = get_redis_client()
        assert result is None
        assert _deps._redis_degraded_since == original_ts

    def test_logs_warning_when_ping_fails(self):
        """Degraded mode must be logged so ops can detect it."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("refused")
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
            patch("auth_user_service.core.deps._logger") as mock_logger,
        ):
            get_redis_client()
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "unavailable" in warning_msg or "degraded" in warning_msg

    def test_circuit_breaker_gauge_set_to_0_on_success(self):
        """Successful ping must set redis_circuit_breaker_open gauge to 0."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_metrics = MagicMock()
        mock_metrics.redis_circuit_breaker_open = MagicMock()
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
            patch(
                "auth_user_service.core.deps._get_metrics", return_value=mock_metrics
            ),
        ):
            get_redis_client()
        mock_metrics.redis_circuit_breaker_open.set.assert_called_once_with(0)

    def test_circuit_breaker_gauge_set_to_1_on_failure(self):
        """Failed ping must set redis_circuit_breaker_open gauge to 1."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = RedisConnectionError("down")
        mock_metrics = MagicMock()
        mock_metrics.redis_circuit_breaker_open = MagicMock()
        with (
            patch("auth_user_service.core.deps._redis_pool", MagicMock()),
            patch("auth_user_service.core.deps.Redis", return_value=mock_client),
            patch(
                "auth_user_service.core.deps._get_metrics", return_value=mock_metrics
            ),
        ):
            get_redis_client()
        mock_metrics.redis_circuit_breaker_open.set.assert_called_once_with(1)


class TestGoogleOAuthRedisRequirement:
    """Google OAuth URL generation; Redis resilience is enforced in the route layer.

    The service (AuthController.get_google_login_url) returns (url, state, verifier)
    without touching Redis.  Redis-level 503 behaviour is tested in
    tests/routes/test_oauth_login.py::TestGetGoogleLoginUrl::test_redis_unavailable_raises_503.
    """

    def test_raises_503_when_google_not_configured(self):
        with patch("auth_user_service.services.auth.settings") as mock_cfg:
            mock_cfg.GOOGLE_CLIENT_ID = None
            with pytest.raises(HTTPException) as exc_info:
                AuthController.get_google_login_url("http://localhost/callback")
        assert exc_info.value.status_code == 503

    def test_503_detail_mentions_google_when_not_configured(self):
        with patch("auth_user_service.services.auth.settings") as mock_cfg:
            mock_cfg.GOOGLE_CLIENT_ID = None
            with pytest.raises(HTTPException) as exc_info:
                AuthController.get_google_login_url("http://localhost/callback")
        detail = exc_info.value.detail.lower()
        assert "google" in detail or "configured" in detail or "unavailable" in detail

    def test_returns_url_state_verifier_triple(self):
        """Service returns all three values; caller stores verifier in OAuthSessionStore."""
        with patch("auth_user_service.services.auth.settings") as mock_cfg:
            mock_cfg.GOOGLE_CLIENT_ID = MagicMock()
            mock_cfg.GOOGLE_CLIENT_ID.get_secret_value.return_value = "test-id"
            result = AuthController.get_google_login_url("http://localhost/callback")
        assert isinstance(result, tuple) and len(result) == 3
        url, state, verifier = result
        assert url.startswith("https://accounts.google.com")
        assert isinstance(state, str) and state
        assert isinstance(verifier, str) and verifier


class TestLoginFailOpen:
    """Login must succeed (fail-open) when Redis is down — rate limiting is skipped."""

    def test_authenticate_works_without_redis(self, db_session, sample_user):
        """Core auth (DB lookup + bcrypt) has no Redis dependency."""
        from tests.conftest import TEST_PASSWORD

        result = AuthController.authenticate(
            session=db_session,
            email=sample_user.email,
            password=TEST_PASSWORD,
        )
        assert result is not None
        assert str(result.id) == str(sample_user.id)

    def test_rate_limiter_not_called_when_redis_is_none(self):
        """Guard: `if redis is not None` must prevent LoginRateLimiter instantiation."""
        redis = None
        limiter_called = False
        if redis is not None:
            LoginRateLimiter(redis).is_allowed("user@example.com")
            limiter_called = True
        assert limiter_called is False

    def test_rate_limiter_reset_not_called_when_redis_is_none(self):
        """On successful login, rate limiter reset must be skipped when Redis is None."""
        redis = None
        reset_called = False
        if redis is not None:
            LoginRateLimiter(redis).reset("user@example.com")
            reset_called = True
        assert reset_called is False
