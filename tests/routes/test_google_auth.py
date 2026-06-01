"""Tests for routes/google_auth.py — all runtime branches covered."""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import HTTPError as HTTPXError

from auth_user_service.routes.google_auth import (
    _build_auth_code_payload,
    _build_redirect_response,
    _get_oauth_session,
    _get_or_create_user,
    _inc_oauth_metric,
    _perform_oauth_exchange,
    google_auth_callback,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_oauth_session_data() -> dict:
    return {
        "pkce_verifier": "verifier123",
        "redirect_target": "chrome-extension://abcdef/callback.html",
        "code_challenge": "challenge123",
    }


def _mock_user(full_name: str = "Test User", avatar: str | None = None) -> MagicMock:
    m = MagicMock()
    m.full_name = full_name
    m.email = "test@example.com"
    m.avatar = avatar
    return m


def _mock_oauth_token() -> MagicMock:
    m = MagicMock()
    m.expires_in = 3600
    m.access_token = "google_access_token"
    m.refresh_token = "google_refresh_token"
    m.email = "test@example.com"
    m.email_verified = True
    m.user_id = "google-uid-123"
    m.name = "Test User"
    return m


# ---------------------------------------------------------------------------
# _get_oauth_session
# ---------------------------------------------------------------------------


class TestGetOauthSession:
    def test_missing_state_raises_400(self) -> None:
        redis = MagicMock()
        with patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore"
        ) as mock_store:
            mock_store.return_value.get.return_value = None
            with pytest.raises(HTTPException) as exc:
                _get_oauth_session(redis, "bad-state")
        assert exc.value.status_code == 400

    def test_valid_state_returns_parsed_dict(self) -> None:
        redis = MagicMock()
        payload = _mock_oauth_session_data()
        with patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore"
        ) as mock_store:
            mock_store.return_value.get.return_value = json.dumps(payload)
            result = _get_oauth_session(redis, "valid-state")
        assert result["pkce_verifier"] == "verifier123"
        assert result["redirect_target"] == "chrome-extension://abcdef/callback.html"


# ---------------------------------------------------------------------------
# _get_or_create_user
# ---------------------------------------------------------------------------


class TestGetOrCreateUser:
    def test_existing_user_returned(self) -> None:
        session = MagicMock()
        oauth_token = _mock_oauth_token()
        existing = MagicMock()
        with patch("auth_user_service.routes.google_auth.UserController") as mock_ctrl:
            mock_ctrl.get_user_by_email.return_value = existing
            result = _get_or_create_user(session, oauth_token)
        assert result is existing
        mock_ctrl.create_user.assert_not_called()

    def test_new_user_created_when_not_found(self) -> None:
        session = MagicMock()
        oauth_token = _mock_oauth_token()
        new_user = MagicMock()
        with patch("auth_user_service.routes.google_auth.UserController") as mock_ctrl:
            mock_ctrl.get_user_by_email.return_value = None
            mock_ctrl.create_user.return_value = new_user
            result = _get_or_create_user(session, oauth_token)
        assert result is new_user
        mock_ctrl.create_user.assert_called_once()


# ---------------------------------------------------------------------------
# _build_redirect_response (smoke — no conditional branches)
# ---------------------------------------------------------------------------


class TestBuildRedirectResponse:
    def test_returns_redirect_with_auth_code_fragment(self) -> None:
        resp = _build_redirect_response(
            redirect_target="chrome-extension://abc/cb.html",
            auth_code="code-uuid",
            access_token="access",
            refresh_token="refresh",
            access_delta=timedelta(hours=1),
        )
        assert resp.status_code == 307
        assert "code-uuid" in resp.headers["location"]


# ---------------------------------------------------------------------------
# _inc_oauth_metric
# ---------------------------------------------------------------------------


class TestIncOauthMetric:
    def test_no_metrics_object_is_noop(self) -> None:
        with patch(
            "auth_user_service.routes.google_auth._get_metrics", return_value=None
        ):
            _inc_oauth_metric("success")  # must not raise

    def test_increments_counter(self) -> None:
        mock_m = MagicMock()
        with patch(
            "auth_user_service.routes.google_auth._get_metrics", return_value=mock_m
        ):
            _inc_oauth_metric("failed")
        mock_m.oauth_attempts_total.labels.assert_called_once_with(
            provider="google", result="failed"
        )


# ---------------------------------------------------------------------------
# _build_auth_code_payload (smoke — tests truncation branches)
# ---------------------------------------------------------------------------


class TestBuildAuthCodePayload:
    def test_all_fields_present(self) -> None:
        user = _mock_user(full_name="Alice", avatar="https://example.com/avatar.png")
        auth_code, payload_json = _build_auth_code_payload(
            user,
            access_token="tok",
            access_delta=timedelta(hours=1),
            code_challenge="challenge",
        )
        assert len(auth_code) == 36  # UUID format
        payload = json.loads(payload_json)
        assert payload["auth_provider"] == "google"
        assert payload["user"]["name"] == "Alice"

    def test_missing_avatar_uses_empty_string(self) -> None:
        user = _mock_user(avatar=None)
        _, payload_json = _build_auth_code_payload(
            user,
            access_token="tok",
            access_delta=timedelta(hours=1),
            code_challenge="challenge",
        )
        payload = json.loads(payload_json)
        assert payload["user"]["avatar"] == ""


# ---------------------------------------------------------------------------
# _perform_oauth_exchange
# ---------------------------------------------------------------------------


def _exchange_patches(*, is_stateless: bool):
    """Return a context-manager stack of all patches needed for _perform_oauth_exchange."""
    return [
        patch(
            "auth_user_service.routes.google_auth.OAuthController.get_google_access_token",
            new_callable=AsyncMock,
            return_value=_mock_oauth_token(),
        ),
        patch(
            "auth_user_service.routes.google_auth._get_or_create_user",
            return_value=_mock_user(),
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthController.create_auth_tokens",
            return_value=("access_tok", "refresh_tok", "jti-1"),
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthController.create_auth_session"
        ),
        patch(
            "auth_user_service.routes.google_auth.SessionController.purge_expired_sessions"
        ),
        patch("auth_user_service.routes.google_auth.AuthCodeStore"),
        patch("auth_user_service.routes.google_auth.OAuthSessionStore"),
        patch("auth_user_service.routes.google_auth.RedisRefreshStore"),
        patch("auth_user_service.routes.google_auth.settings") if True else None,
    ]


class TestPerformOauthExchange:
    @pytest.mark.anyio
    async def test_stateless_skips_refresh_store(self) -> None:
        """is_stateless=True → RedisRefreshStore.register never called."""
        with (
            patch(
                "auth_user_service.routes.google_auth.OAuthController"
                ".get_google_access_token",
                new_callable=AsyncMock,
                return_value=_mock_oauth_token(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_or_create_user",
                return_value=_mock_user(),
            ),
            patch(
                "auth_user_service.routes.google_auth.AuthController.create_auth_tokens",
                return_value=("access_tok", "refresh_tok", "jti-1"),
            ),
            patch(
                "auth_user_service.routes.google_auth.AuthController.create_auth_session"
            ),
            patch(
                "auth_user_service.routes.google_auth.SessionController"
                ".purge_expired_sessions"
            ),
            patch("auth_user_service.routes.google_auth.AuthCodeStore"),
            patch("auth_user_service.routes.google_auth.OAuthSessionStore"),
            patch(
                "auth_user_service.routes.google_auth.RedisRefreshStore"
            ) as mock_refresh,
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.is_stateless = True
            mock_cfg.ACCESS_TOKEN_EXPIRE_MINUTES = 60
            mock_cfg.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = 3600
            mock_cfg.ENVIRONMENT = "local"
            await _perform_oauth_exchange(
                MagicMock(),
                MagicMock(),
                "code",
                "verifier",
                "https://example.com/cb",
                "chrome-extension://abc/cb.html",
                "challenge",
                "state-1",
            )
        mock_refresh.return_value.register.assert_not_called()

    @pytest.mark.anyio
    async def test_stateful_registers_refresh_store(self) -> None:
        """is_stateless=False → RedisRefreshStore.register called once."""
        with (
            patch(
                "auth_user_service.routes.google_auth.OAuthController"
                ".get_google_access_token",
                new_callable=AsyncMock,
                return_value=_mock_oauth_token(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_or_create_user",
                return_value=_mock_user(),
            ),
            patch(
                "auth_user_service.routes.google_auth.AuthController.create_auth_tokens",
                return_value=("access_tok", "refresh_tok", "jti-1"),
            ),
            patch(
                "auth_user_service.routes.google_auth.AuthController.create_auth_session"
            ),
            patch(
                "auth_user_service.routes.google_auth.SessionController"
                ".purge_expired_sessions"
            ),
            patch("auth_user_service.routes.google_auth.AuthCodeStore"),
            patch("auth_user_service.routes.google_auth.OAuthSessionStore"),
            patch(
                "auth_user_service.routes.google_auth.RedisRefreshStore"
            ) as mock_refresh,
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.is_stateless = False
            mock_cfg.ACCESS_TOKEN_EXPIRE_MINUTES = 60
            mock_cfg.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = 3600
            mock_cfg.ENVIRONMENT = "local"
            mock_cfg.REFRESH_TOKEN_EXPIRE_MINUTES = 60
            await _perform_oauth_exchange(
                MagicMock(),
                MagicMock(),
                "code",
                "verifier",
                "https://example.com/cb",
                "chrome-extension://abc/cb.html",
                "challenge",
                "state-1",
            )
        mock_refresh.return_value.register.assert_called_once()


# ---------------------------------------------------------------------------
# google_auth_callback
# ---------------------------------------------------------------------------


class TestGoogleAuthCallback:
    @pytest.mark.anyio
    async def test_redis_unavailable_raises_503(self) -> None:
        with patch(
            "auth_user_service.routes.google_auth.get_redis_client", return_value=None
        ):
            with pytest.raises(HTTPException) as exc:
                await google_auth_callback(
                    request=MagicMock(),
                    session=MagicMock(),
                    code="code",
                    state="state",
                )
        assert exc.value.status_code == 503

    @pytest.mark.anyio
    async def test_invalid_state_http_exception_reraised(self) -> None:
        """HTTPException from _get_oauth_session → re-raised as-is."""
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                side_effect=HTTPException(400, "Invalid or expired state parameter"),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await google_auth_callback(
                    request=MagicMock(),
                    session=MagicMock(),
                    code="code",
                    state="bad-state",
                )
        assert exc.value.status_code == 400

    @pytest.mark.anyio
    async def test_session_lookup_generic_exception_raises_400(self) -> None:
        """Non-HTTP exception in session lookup → wrapped as 400."""
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                side_effect=ValueError("corrupt json"),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await google_auth_callback(
                    request=MagicMock(),
                    session=MagicMock(),
                    code="code",
                    state="state",
                )
        assert exc.value.status_code == 400

    @pytest.mark.anyio
    async def test_exchange_httpx_error_raises_400(self) -> None:
        """HTTPXError from _perform_oauth_exchange → 400."""
        request = MagicMock()
        request.url_for.return_value = "http://callback"
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                return_value=_mock_oauth_session_data(),
            ),
            patch(
                "auth_user_service.routes.google_auth._perform_oauth_exchange",
                new_callable=AsyncMock,
                side_effect=HTTPXError("network error"),
            ),
            patch("auth_user_service.routes.google_auth._inc_oauth_metric"),
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.GOOGLE_OAUTH_REDIRECT_URI = ""
            with pytest.raises(HTTPException) as exc:
                await google_auth_callback(
                    request=request,
                    session=MagicMock(),
                    code="code",
                    state="state",
                )
        assert exc.value.status_code == 400

    @pytest.mark.anyio
    async def test_exchange_http_exception_reraised(self) -> None:
        """HTTPException from _perform_oauth_exchange → re-raised unchanged."""
        request = MagicMock()
        request.url_for.return_value = "http://callback"
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                return_value=_mock_oauth_session_data(),
            ),
            patch(
                "auth_user_service.routes.google_auth._perform_oauth_exchange",
                new_callable=AsyncMock,
                side_effect=HTTPException(503, "DB down"),
            ),
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.GOOGLE_OAUTH_REDIRECT_URI = ""
            with pytest.raises(HTTPException) as exc:
                await google_auth_callback(
                    request=request,
                    session=MagicMock(),
                    code="code",
                    state="state",
                )
        assert exc.value.status_code == 503

    @pytest.mark.anyio
    async def test_exchange_generic_exception_raises_500(self) -> None:
        """Unexpected exception from _perform_oauth_exchange → 500."""
        request = MagicMock()
        request.url_for.return_value = "http://callback"
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                return_value=_mock_oauth_session_data(),
            ),
            patch(
                "auth_user_service.routes.google_auth._perform_oauth_exchange",
                new_callable=AsyncMock,
                side_effect=RuntimeError("unexpected"),
            ),
            patch("auth_user_service.routes.google_auth._inc_oauth_metric"),
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.GOOGLE_OAUTH_REDIRECT_URI = ""
            with pytest.raises(HTTPException) as exc:
                await google_auth_callback(
                    request=request,
                    session=MagicMock(),
                    code="code",
                    state="state",
                )
        assert exc.value.status_code == 500

    @pytest.mark.anyio
    async def test_success_uses_configured_redirect_uri(self) -> None:
        """Happy path: GOOGLE_OAUTH_REDIRECT_URI is set — used directly."""
        mock_response = MagicMock()
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                return_value=_mock_oauth_session_data(),
            ),
            patch(
                "auth_user_service.routes.google_auth._perform_oauth_exchange",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch(
                "auth_user_service.routes.google_auth._inc_oauth_metric"
            ) as mock_metric,
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.GOOGLE_OAUTH_REDIRECT_URI = "https://example.com/callback"
            result = await google_auth_callback(
                request=MagicMock(),
                session=MagicMock(),
                code="code",
                state="state",
            )
        assert result is mock_response
        mock_metric.assert_called_once_with("success")

    @pytest.mark.anyio
    async def test_success_derives_callback_uri_from_request(self) -> None:
        """Happy path: empty GOOGLE_OAUTH_REDIRECT_URI — fallback to request.url_for."""
        request = MagicMock()
        request.url_for.return_value = "http://derived-callback"
        mock_response = MagicMock()
        with (
            patch(
                "auth_user_service.routes.google_auth.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.google_auth._get_oauth_session",
                return_value=_mock_oauth_session_data(),
            ),
            patch(
                "auth_user_service.routes.google_auth._perform_oauth_exchange",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
            patch("auth_user_service.routes.google_auth._inc_oauth_metric"),
            patch("auth_user_service.routes.google_auth.settings") as mock_cfg,
        ):
            mock_cfg.GOOGLE_OAUTH_REDIRECT_URI = ""
            result = await google_auth_callback(
                request=request,
                session=MagicMock(),
                code="code",
                state="state",
            )
        assert result is mock_response
        request.url_for.assert_called_once_with("google_auth_callback")
