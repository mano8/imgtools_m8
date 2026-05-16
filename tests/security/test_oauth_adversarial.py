"""Security regression: PKCE OAuth adversarial scenarios.

Verifies that:
- PKCEStore.pop() uses GETDEL (atomic) not GET+DELETE (racy)
- A second pop() with the same state returns None (replay prevention)
- A concurrent second pop simulated by GETDEL returning None is rejected
- An unknown / never-registered state returns None from pop()
- An expired state (TTL elapsed) returns None from pop() (same as unknown)
- The callback returns 503 when Redis is down at callback time
- The callback returns 400 for an unknown / consumed state parameter
- The callback returns 400 when the state was stored but the verifier is gone
- store() registers the key with the correct prefix and TTL
- Successful OAuth callback registers the refresh JTI in the Redis allowlist
- Stateless mode skips allowlist registration
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

import pytest

from auth_user_service.core.client import PKCEStore
from auth_user_service.routes.google_auth import google_auth_callback


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# PKCEStore unit tests
# ---------------------------------------------------------------------------


class TestPKCEStoreAtomicity:
    """pop() must use GETDEL — not separate GET + DELETE — to be race-free."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = PKCEStore(self.mock_redis)

    def test_store_sets_key_with_prefix(self):
        self.store.store("my-state", "verifier123")
        key_used = self.mock_redis.setex.call_args[0][0]
        assert key_used == "pkce:my-state"

    def test_store_sets_ttl_to_10_minutes(self):
        from datetime import timedelta

        self.store.store("my-state", "verifier123")
        ttl_arg = self.mock_redis.setex.call_args[0][1]
        assert ttl_arg == timedelta(minutes=10)

    def test_pop_uses_getdel_not_get(self):
        """Atomicity requirement: must use GETDEL, never plain GET."""
        self.mock_redis.getdel.return_value = b"verifier-value"
        self.store.pop("my-state")
        self.mock_redis.getdel.assert_called_once_with("pkce:my-state")
        self.mock_redis.get.assert_not_called()

    def test_pop_does_not_call_delete_separately(self):
        """GETDEL is the only operation — no standalone DELETE call."""
        self.mock_redis.getdel.return_value = b"verifier-value"
        self.store.pop("my-state")
        self.mock_redis.delete.assert_not_called()

    def test_pop_returns_verifier_when_present(self):
        self.mock_redis.getdel.return_value = b"my-verifier"
        result = self.store.pop("my-state")
        assert result == b"my-verifier"

    def test_pop_returns_none_when_key_absent(self):
        """Unknown or already-consumed state → None."""
        self.mock_redis.getdel.return_value = None
        result = self.store.pop("unknown-state")
        assert result is None


class TestPKCEReplayPrevention:
    """A consumed state must not yield a verifier on a second attempt."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.store = PKCEStore(self.mock_redis)

    def test_first_pop_returns_verifier(self):
        self.mock_redis.getdel.return_value = b"verifier-abc"
        assert self.store.pop("state-xyz") == b"verifier-abc"

    def test_second_pop_returns_none(self):
        """After GETDEL consumed the key, the second call finds nothing."""
        self.mock_redis.getdel.side_effect = [b"verifier-abc", None]
        self.store.pop("state-xyz")
        result = self.store.pop("state-xyz")
        assert result is None

    def test_expired_state_returns_none(self):
        """Redis TTL-expired key behaves identically to an absent key."""
        self.mock_redis.getdel.return_value = None
        assert self.store.pop("expired-state") is None

    def test_concurrent_second_request_gets_none(self):
        """Simulate the losing concurrent tab: GETDEL returns None because
        the winning request already atomically consumed the key."""
        self.mock_redis.getdel.return_value = None  # first caller already took it
        result = self.store.pop("contested-state")
        assert result is None


# ---------------------------------------------------------------------------
# OAuth callback route-level tests (direct async invocation, no middleware)
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


@pytest.mark.anyio
async def test_unknown_state_raises_400():
    """State never stored in Redis (GETDEL returns None) → 400."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.pop.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.PKCEStore",
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
    """GETDEL already consumed the key on first request → second gets None → 400."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.pop.return_value = None  # first caller already took it

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.PKCEStore",
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
    """State TTL expired before callback arrived → GETDEL returns None → 400."""
    mock_request = MagicMock()
    mock_session = MagicMock()
    mock_redis = MagicMock()
    mock_store = MagicMock()
    mock_store.pop.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.PKCEStore",
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
    mock_store.pop.return_value = None

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch(
            "auth_user_service.routes.google_auth.PKCEStore",
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
# Allowlist registration — Fix #2 regression tests
# ---------------------------------------------------------------------------


def _make_oauth_mocks():
    """Return a consistent set of mocks for a full successful OAuth callback."""
    request = MagicMock()
    request.url_for.return_value = "http://testserver/success/123"

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

    return request, oauth_token, session_data


@pytest.mark.anyio
async def test_successful_oauth_registers_refresh_jti_in_allowlist():
    """A stateful OAuth login must register the refresh JTI so rotation works."""
    request, oauth_token, session_data = _make_oauth_mocks()
    mock_redis = MagicMock()
    mock_pkce = MagicMock()
    mock_pkce.pop.return_value = "code-verifier"
    mock_user = MagicMock()
    mock_refresh_store = MagicMock()

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch("auth_user_service.routes.google_auth.PKCEStore", return_value=mock_pkce),
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
    request, oauth_token, session_data = _make_oauth_mocks()
    mock_redis = MagicMock()
    mock_pkce = MagicMock()
    mock_pkce.pop.return_value = "code-verifier"
    mock_user = MagicMock()
    mock_refresh_store = MagicMock()

    with (
        patch(
            "auth_user_service.routes.google_auth.get_redis_client",
            return_value=mock_redis,
        ),
        patch("auth_user_service.routes.google_auth.PKCEStore", return_value=mock_pkce),
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
        mock_settings.ENVIRONMENT = "local"
        mock_settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS = 604800
        mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30

        await google_auth_callback(
            request=request,
            session=MagicMock(),
            code="auth-code",
            state="valid-state",
        )

    mock_refresh_store.register.assert_not_called()
