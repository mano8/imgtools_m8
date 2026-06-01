"""Security regression: forced-churn detection on refresh token reuse.

Verifies that when the Lua rotation script detects a consumed JTI (reuse attack):
- session_integrity_denial_total counter is emitted with trigger=reuse_detected
- Logger emits CRITICAL (not WARNING) with structured event fields
- revoke_all_user_sessions is called to chain-invalidate all victim sessions
- The attacker IP is present in the log event
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from auth_sdk_m8.schemas.auth import TokenMinimalData, TokenSecret
from auth_user_service.core.security import SecurityHelper
from auth_user_service.routes.login import login_refresh_token


def _make_refresh_token(user_id: str | None = None) -> str:
    from auth_user_service.core.config import settings

    uid = user_id or str(uuid.uuid4())
    data = TokenMinimalData(sub=uid)
    refresh_secret = TokenSecret(
        secret_key=settings.REFRESH_SECRET_KEY,
        algorithm=settings.REFRESH_TOKEN_ALGORITHM,
    )
    refresh_token, _ = SecurityHelper.create_refresh_token(
        data=data,
        expires_delta=timedelta(days=1),
        secrets=refresh_secret,
    )
    return refresh_token


class TestForcedChurnDetection:
    def _run_reuse_scenario(
        self, mock_metrics: MagicMock | None = None
    ) -> tuple[MagicMock, MagicMock]:
        """Run login_refresh_token with rotate=False and return (mock_logger, mock_revoke)."""
        refresh_token = _make_refresh_token()

        mock_request = MagicMock()
        mock_request.headers.get.return_value = "10.0.0.1"
        mock_request.client.host = "10.0.0.1"

        mock_response = MagicMock()
        mock_redis = MagicMock()
        mock_session = MagicMock()

        mock_user = MagicMock()
        mock_user.is_active = True

        with (
            patch("auth_user_service.routes.login.settings") as mock_cfg,
            patch("auth_user_service.routes.login.RefreshRateLimiter") as mock_rl_cls,
            patch("auth_user_service.routes.login.RedisRefreshStore") as mock_store_cls,
            patch(
                "auth_user_service.routes.login.UserController.get_user",
                return_value=mock_user,
            ),
            patch(
                "auth_user_service.routes.login.AuthController.create_auth_tokens",
                return_value=("at", "rt", "new-jti"),
            ),
            patch(
                "auth_user_service.routes.login.SessionController.revoke_all_user_sessions"
            ) as mock_revoke,
            patch("auth_user_service.routes.login.logger") as mock_logger,
            patch(
                "auth_user_service.routes.login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            mock_cfg.is_stateless = False
            mock_cfg.REFRESH_SECRET_KEY = MagicMock()
            mock_cfg.REFRESH_TOKEN_ALGORITHM = "HS256"
            mock_cfg.effective_failure_mode.return_value = "fail_open"
            mock_cfg.TRUSTED_PROXY_COUNT = 1

            from auth_user_service.core.config import settings as real_settings

            mock_cfg.REFRESH_SECRET_KEY = real_settings.REFRESH_SECRET_KEY
            mock_cfg.REFRESH_TOKEN_ALGORITHM = real_settings.REFRESH_TOKEN_ALGORITHM

            # Rate limiter: allow
            mock_rl_cls.return_value.is_allowed.return_value = True
            # is_valid: JTI present in allowlist
            mock_store_instance = MagicMock()
            mock_store_instance.is_valid.return_value = True
            # rotate: returns False → reuse detected
            mock_store_instance.rotate.return_value = False
            mock_store_cls.return_value = mock_store_instance

            with pytest.raises(HTTPException) as exc_info:
                login_refresh_token(
                    request=mock_request,
                    response=mock_response,
                    session=mock_session,
                    redis=mock_redis,
                    refresh_token=refresh_token,
                )

        assert exc_info.value.status_code == 401
        return mock_logger, mock_revoke

    def test_reuse_emits_critical_log(self):
        """Token reuse must log CRITICAL, not WARNING."""
        mock_logger, _ = self._run_reuse_scenario()
        mock_logger.critical.assert_called_once()
        log_args = mock_logger.critical.call_args[0]
        assert "session.integrity_denial" in log_args[0]
        assert "reuse_detected" in log_args[0]
        assert "attacker_ip" in log_args[0]

    def test_reuse_calls_revoke_all_user_sessions(self):
        """Chain invalidation must fire when reuse is detected."""
        _, mock_revoke = self._run_reuse_scenario()
        mock_revoke.assert_called_once()

    def test_reuse_emits_session_integrity_denial_counter(self):
        """session_integrity_denial_total must be incremented with trigger=reuse_detected."""
        mock_metrics = MagicMock()
        mock_metrics.session_integrity_denial_total = MagicMock()
        mock_metrics.token_refresh_total = MagicMock()

        self._run_reuse_scenario(mock_metrics=mock_metrics)

        mock_metrics.session_integrity_denial_total.labels.assert_called_once_with(
            trigger="reuse_detected"
        )
        mock_metrics.session_integrity_denial_total.labels.return_value.inc.assert_called_once()

    def test_reuse_no_warning_only_critical(self):
        """logger.warning must NOT be called — only logger.critical."""
        mock_logger, _ = self._run_reuse_scenario()
        mock_logger.warning.assert_not_called()
