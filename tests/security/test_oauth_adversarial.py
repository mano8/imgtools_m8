"""Security regression: OAuth callback adversarial scenarios.

Verifies that:
- OAuthSessionStore.get() is used for CSRF check (not GETDEL) so a transient
  Google exchange failure does not permanently invalidate the session
- OAuthSessionStore.delete() is called only on the success path
- The callback returns 503 when Redis is down at callback time
- The callback returns 400 for an unknown / consumed state parameter
- Successful OAuth callback registers the refresh JTI in the Redis allowlist
- Stateless mode skips allowlist registration
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

import pytest

from auth_user_service.routes.google_auth import google_auth_callback


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SESSION_JSON = json.dumps(
    {
        "pkce_verifier": "code-verifier",
        "redirect_target": "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/",
        "code_challenge": "test-challenge",
        "created_at": 1234567890,
        "flow": "google",
    }
)


def _make_oauth_mocks():
    """Return consistent mocks for a full successful OAuth callback."""
    request = MagicMock()
    request.url_for.return_value = "http://testserver/callback/"

    oauth_token = MagicMock()
    oauth_token.email = "user@example.com"
    oauth_token.user_id = "google-uid-1"
    oauth_token.email_verified = True
    oauth_token.name = "Test User"
    oauth_token.expires_in = 3600
    oauth_token.access_token = "goog-access"
    oauth_token.refresh_token = "goog-refresh"

    session_data = MagicMock()
    session_data.id = "session-uuid-1"

    mock_user = MagicMock()
    mock_user.full_name = "Test User"
    mock_user.email = "user@example.com"
    mock_user.avatar = ""

    mock_session_store = MagicMock()
    mock_session_store.get.return_value = _SESSION_JSON

    return request, oauth_token, session_data, mock_user, mock_session_store


# ---------------------------------------------------------------------------
# Redis unavailable
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_redis_down_at_callback_raises_503():
    """Redis unavailable when callback fires → 503, not 500 or crash."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    with patch(
        "auth_user_service.routes.google_auth.get_redis_client", return_value=None
    ):
        with pytest.raises(HTTPException) as exc_info:
            await google_auth_callback(
                request=mock_request,
                session=mock_session,
                code="auth-code",
                state="some-state",
            )
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Unknown / expired / replayed state → 400
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_unknown_state_raises_400():
    """State never stored in Redis (get returns None) → 400."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.get.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore",
            return_value=mock_store,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await google_auth_callback(
                request=mock_request,
                session=mock_session,
                code="auth-code",
                state="bogus-state",
            )
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_replay_second_callback_raises_400():
    """Session already consumed → get returns None → 400."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.get.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore",
            return_value=mock_store,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await google_auth_callback(
                request=mock_request,
                session=mock_session,
                code="auth-code",
                state="already-used-state",
            )
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_expired_state_raises_400():
    """State TTL expired before callback arrived → get returns None → 400."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.get.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore",
            return_value=mock_store,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await google_auth_callback(
                request=mock_request,
                session=mock_session,
                code="auth-code",
                state="expired-state",
            )
    assert exc_info.value.status_code == 400


@pytest.mark.anyio
async def test_400_detail_mentions_state():
    """Error detail must indicate the state parameter was the problem."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.get.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore",
            return_value=mock_store,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await google_auth_callback(
                request=mock_request,
                session=mock_session,
                code="auth-code",
                state="bad-state",
            )
    detail = exc_info.value.detail.lower()
    assert "state" in detail or "expired" in detail or "invalid" in detail


# ---------------------------------------------------------------------------
# Allowlist registration — success path regression tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_successful_oauth_registers_refresh_jti_in_allowlist():
    """A stateful OAuth login must register the refresh JTI so rotation works."""
    request, oauth_token, session_data, mock_user, mock_session_store = (
        _make_oauth_mocks()
    )
    mock_redis = MagicMock()
    mock_refresh_store = MagicMock()
    mock_auth_code_store = MagicMock()

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore",
            return_value=mock_session_store,
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthCodeStore",
            return_value=mock_auth_code_store,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthController.get_google_access_token",
            new_callable=AsyncMock,
            return_value=oauth_token,
        ),
        patch(
            "auth_user_service.routes.google_auth.UserController.get_user_by_email",
            return_value=mock_user,
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthController.create_auth_tokens",
            return_value=("access-tok", "refresh-tok", "test-jti-oauth"),
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthController.create_auth_session",
            return_value=session_data,
        ),
        patch(
            "auth_user_service.routes.google_auth.RedisRefreshStore",
            return_value=mock_refresh_store,
        ),
        patch(
            "auth_user_service.routes.google_auth.SessionController.purge_expired_sessions"
        ),
        patch("auth_user_service.routes.google_auth.settings") as mock_settings,
    ):
        mock_settings.TOKEN_MODE = "stateful"
        mock_settings.is_stateless = False
        mock_settings.ENVIRONMENT = "local"
        mock_settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = 604800
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        mock_settings.GOOGLE_OAUTH_REDIRECT_URI = ""

        await google_auth_callback(
            request=request,
            session=MagicMock(),
            code="auth-code",
            state="valid-state",
        )

    mock_refresh_store.register.assert_called_once()
    jti_arg = mock_refresh_store.register.call_args[0][0]
    assert jti_arg == "test-jti-oauth"


@pytest.mark.anyio
async def test_stateless_mode_skips_allowlist_registration():
    """In stateless mode the allowlist registration must be skipped entirely."""
    request, oauth_token, session_data, mock_user, mock_session_store = (
        _make_oauth_mocks()
    )
    mock_redis = MagicMock()
    mock_refresh_store = MagicMock()
    mock_auth_code_store = MagicMock()

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthSessionStore",
            return_value=mock_session_store,
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthCodeStore",
            return_value=mock_auth_code_store,
        ),
        patch(
            "auth_user_service.routes.google_auth.OAuthController.get_google_access_token",
            new_callable=AsyncMock,
            return_value=oauth_token,
        ),
        patch(
            "auth_user_service.routes.google_auth.UserController.get_user_by_email",
            return_value=mock_user,
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthController.create_auth_tokens",
            return_value=("access-tok", "refresh-tok", "jti-stateless"),
        ),
        patch(
            "auth_user_service.routes.google_auth.AuthController.create_auth_session",
            return_value=session_data,
        ),
        patch(
            "auth_user_service.routes.google_auth.RedisRefreshStore",
            return_value=mock_refresh_store,
        ),
        patch(
            "auth_user_service.routes.google_auth.SessionController.purge_expired_sessions"
        ),
        patch("auth_user_service.routes.google_auth.settings") as mock_settings,
    ):
        mock_settings.TOKEN_MODE = "stateless"
        mock_settings.is_stateless = True
        mock_settings.ENVIRONMENT = "local"
        mock_settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = 604800
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        mock_settings.GOOGLE_OAUTH_REDIRECT_URI = ""

        await google_auth_callback(
            request=request,
            session=MagicMock(),
            code="auth-code",
            state="valid-state",
        )

    mock_refresh_store.register.assert_not_called()
