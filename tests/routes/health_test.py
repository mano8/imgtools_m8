"""Unit tests for the health check endpoint."""

from unittest.mock import MagicMock, patch

from auth_user_service.routes.health import health_check


class TestHealthCheck:
    def _mock_db_ok(self):
        """Return a context manager that simulates a successful DB SELECT 1."""
        mock_conn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_ctx
        return mock_engine

    def test_all_healthy_returns_ok(self):
        mock_engine = self._mock_db_ok()
        with (
            patch("auth_user_service.routes.health.settings") as mock_cfg,
            patch(
                "auth_user_service.routes.health.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.health.get_redis_degraded_since",
                return_value=None,
            ),
            patch("auth_user_service.routes.health.engine", mock_engine),
        ):
            mock_cfg.requires_redis = True
            mock_cfg.TOKEN_MODE = "stateful"
            mock_cfg.effective_failure_mode.side_effect = lambda c: "fail_closed"

            result = health_check()

        assert result["status"] == "ok"
        assert result["redis"] == "ok"
        assert result["database"] == "ok"
        assert result["circuit_breaker"] == "closed"
        assert result["effective_mode"] == "stateful"

    def test_redis_unavailable_opens_circuit_breaker(self):
        mock_engine = self._mock_db_ok()
        with (
            patch("auth_user_service.routes.health.settings") as mock_cfg,
            patch(
                "auth_user_service.routes.health.get_redis_client", return_value=None
            ),
            patch(
                "auth_user_service.routes.health.get_redis_degraded_since",
                return_value=None,
            ),
            patch("auth_user_service.routes.health.engine", mock_engine),
        ):
            mock_cfg.requires_redis = True
            mock_cfg.TOKEN_MODE = "stateful"
            mock_cfg.effective_failure_mode.side_effect = lambda c: "fail_closed"

            result = health_check()

        assert result["status"] == "degraded"
        assert result["redis"] == "unavailable"
        assert result["circuit_breaker"] == "open"
        assert result["effective_mode"] == "stateless_degraded"
        assert result["revocation_available"] is False
        assert result["rate_limiting_available"] is False

    def test_redis_not_required_circuit_breaker_closed(self):
        mock_engine = self._mock_db_ok()
        with (
            patch("auth_user_service.routes.health.settings") as mock_cfg,
            patch("auth_user_service.routes.health.get_redis_client") as mock_get_redis,
            patch(
                "auth_user_service.routes.health.get_redis_degraded_since",
                return_value=None,
            ),
            patch("auth_user_service.routes.health.engine", mock_engine),
        ):
            mock_cfg.requires_redis = False
            mock_cfg.TOKEN_MODE = "stateless"
            mock_cfg.effective_failure_mode.side_effect = lambda c: "fail_open"

            result = health_check()

        mock_get_redis.assert_not_called()
        assert result["circuit_breaker"] == "closed"
        assert result["status"] == "ok"

    def test_degradation_modes_included_in_response(self):
        mock_engine = self._mock_db_ok()
        with (
            patch("auth_user_service.routes.health.settings") as mock_cfg,
            patch(
                "auth_user_service.routes.health.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.health.get_redis_degraded_since",
                return_value=None,
            ),
            patch("auth_user_service.routes.health.engine", mock_engine),
        ):
            mock_cfg.requires_redis = True
            mock_cfg.TOKEN_MODE = "stateful"
            mock_cfg.effective_failure_mode.side_effect = lambda c: (
                "fail_closed"
                if c in ("refresh_validation", "session_write")
                else "fail_open"
            )

            result = health_check()

        modes = result["degradation_modes"]
        assert modes["rate_limit"] == "fail_open"
        assert modes["refresh_validation"] == "fail_closed"
        assert modes["session_write"] == "fail_closed"
        assert modes["access_revocation"] == "fail_open"

    def test_database_unavailable_returns_degraded(self):
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = Exception("DB down")
        with (
            patch("auth_user_service.routes.health.settings") as mock_cfg,
            patch(
                "auth_user_service.routes.health.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.health.get_redis_degraded_since",
                return_value=None,
            ),
            patch("auth_user_service.routes.health.engine", mock_engine),
        ):
            mock_cfg.requires_redis = True
            mock_cfg.TOKEN_MODE = "stateful"
            mock_cfg.effective_failure_mode.side_effect = lambda c: "fail_open"

            result = health_check()

        assert result["status"] == "degraded"
        assert result["database"] == "unavailable"
        assert result["circuit_breaker"] == "closed"
