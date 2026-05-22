"""Tests for routes/oauth_login.py — 100% branch coverage."""

import base64
import hashlib
import json
import uuid as _uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from auth_user_service.routes.oauth_login import (
    ExchangeRequest,
    _build_cors_origin_regex,
    _uri_prefix_match_any,
    _verify_pkce,
    exchange_auth_code,
    get_google_login_url,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_challenge(verifier: str) -> str:
    """Compute RFC 7636 S256 PKCE challenge from a verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


_VALID_VERIFIER = "x" * 43
_VALID_CHALLENGE = _compute_challenge(_VALID_VERIFIER)
# Valid redirect_target for tests (chrome-extension scheme, 32-char host, path)
_VALID_REDIRECT = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/callback.html"
# code_challenge accepted by the login-url endpoint (A-Z 43 chars)
_VALID_CODE_CHALLENGE = "A" * 43


def _login_settings(**overrides):
    """Mock settings for get_google_login_url tests."""
    m = MagicMock()
    m.OAUTH_ALLOWED_REDIRECT_SCHEMES = ["chrome-extension://"]
    m.OAUTH_ALLOWED_REDIRECT_PREFIXES = []
    m.GOOGLE_OAUTH_REDIRECT_URI = ""
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _exchange_settings(**overrides):
    """Mock settings for exchange_auth_code tests."""
    m = MagicMock()
    m.CORS_ALLOWED_ORIGIN_SCHEMES = []
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _mock_request(origin: str = "", client_host: str = "127.0.0.1") -> MagicMock:
    req = MagicMock()
    req.client.host = client_host
    req.headers.get.return_value = origin
    return req


def _valid_exchange_payload(challenge: str = _VALID_CHALLENGE) -> str:
    """Build a realistic auth_code Redis payload for exchange tests."""
    return json.dumps(
        {
            "version": 1,
            "auth_provider": "google",
            "access_token": "tok-123",
            "expires_at": 1700000000000,
            "user": {"name": "User", "email": "u@x.com", "avatar": ""},
            "code_challenge": challenge,
        }
    )


def _mock_rate_limiter(allowed: bool = True) -> MagicMock:
    m = MagicMock()
    m.is_allowed.return_value = allowed
    return m


# ---------------------------------------------------------------------------
# _build_cors_origin_regex
# ---------------------------------------------------------------------------


class TestBuildCorsOriginRegex:
    def test_empty_schemes_returns_none(self):
        assert _build_cors_origin_regex([]) is None

    def test_chrome_extension_returns_regex_string(self):
        result = _build_cors_origin_regex(["chrome-extension://"])
        assert result is not None
        assert "chrome-extension" in result

    def test_unsupported_scheme_returns_none(self):
        assert _build_cors_origin_regex(["other://"]) is None

    def test_regex_matches_32char_extension_id(self):
        import re

        regex = _build_cors_origin_regex(["chrome-extension://"])
        assert re.fullmatch(regex, "chrome-extension://" + "a" * 32) is not None

    def test_regex_rejects_https_origin(self):
        import re

        regex = _build_cors_origin_regex(["chrome-extension://"])
        assert re.fullmatch(regex, "https://evil.com") is None


# ---------------------------------------------------------------------------
# _verify_pkce
# ---------------------------------------------------------------------------


class TestVerifyPkce:
    def test_correct_pair_returns_true(self):
        assert _verify_pkce(_VALID_VERIFIER, _VALID_CHALLENGE) is True

    def test_wrong_challenge_returns_false(self):
        assert _verify_pkce(_VALID_VERIFIER, "W" * 43) is False


# ---------------------------------------------------------------------------
# _uri_prefix_match_any
# ---------------------------------------------------------------------------


class TestUriPrefixMatchAny:
    def test_empty_prefixes_returns_false(self):
        assert _uri_prefix_match_any(_VALID_REDIRECT, []) is False

    def test_matching_prefix_returns_true(self):
        prefix = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        assert _uri_prefix_match_any(_VALID_REDIRECT, [prefix]) is True

    def test_target_path_with_trailing_slash_matches(self):
        target = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        prefix = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        assert _uri_prefix_match_any(target, [prefix]) is True

    def test_target_path_without_trailing_slash_matches(self):
        target = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/callback"
        prefix = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        assert _uri_prefix_match_any(target, [prefix]) is True

    def test_scheme_mismatch_returns_false(self):
        target = "myapp://abcdefghijklmnopqrstuvwxyzabcdef/callback"
        prefix = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        assert _uri_prefix_match_any(target, [prefix]) is False

    def test_netloc_mismatch_returns_false(self):
        target = "chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz/callback"
        prefix = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        assert _uri_prefix_match_any(target, [prefix]) is False

    def test_path_mismatch_returns_false(self):
        target = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/other"
        prefix = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/restricted/"
        assert _uri_prefix_match_any(target, [prefix]) is False

    def test_first_prefix_no_match_second_matches(self):
        wrong = "chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz/"
        right = "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
        assert _uri_prefix_match_any(_VALID_REDIRECT, [wrong, right]) is True


# ---------------------------------------------------------------------------
# get_google_login_url
# ---------------------------------------------------------------------------


class TestGetGoogleLoginUrl:
    @pytest.mark.anyio
    async def test_missing_redirect_target_raises_400(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url()
        assert exc.value.status_code == 400
        assert "redirect_target" in exc.value.detail

    @pytest.mark.anyio
    async def test_redirect_target_too_long_raises_400(self):
        long_target = (
            "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/" + "x" * 2050
        )
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target=long_target,
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "too long" in exc.value.detail

    @pytest.mark.anyio
    async def test_missing_code_challenge_raises_400(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(redirect_target=_VALID_REDIRECT)
        assert exc.value.status_code == 400
        assert "code_challenge" in exc.value.detail

    @pytest.mark.anyio
    async def test_invalid_code_challenge_format_raises_400(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target=_VALID_REDIRECT,
                    code_challenge="!!invalid!!",
                )
        assert exc.value.status_code == 400
        assert "code_challenge" in exc.value.detail

    @pytest.mark.anyio
    async def test_http_redirect_hard_rejected(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target="http://evil.com/callback",
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "web origins" in exc.value.detail

    @pytest.mark.anyio
    async def test_https_redirect_hard_rejected(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target="https://evil.com/callback",
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "web origins" in exc.value.detail

    @pytest.mark.anyio
    async def test_disallowed_scheme_raises_400(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target="myapp://host/callback",
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "scheme not allowed" in exc.value.detail

    @pytest.mark.anyio
    async def test_empty_netloc_raises_400(self):
        with patch("auth_user_service.routes.oauth_login.settings", _login_settings()):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target="chrome-extension://",
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "host" in exc.value.detail

    @pytest.mark.anyio
    async def test_prefix_allowlist_rejects_non_matching(self):
        s = _login_settings(
            OAUTH_ALLOWED_REDIRECT_PREFIXES=[
                "chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz/"
            ]
        )
        with patch("auth_user_service.routes.oauth_login.settings", s):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target=_VALID_REDIRECT,
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "prefixes" in exc.value.detail

    @pytest.mark.anyio
    async def test_redis_unavailable_raises_503(self):
        with (
            patch("auth_user_service.routes.oauth_login.settings", _login_settings()),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=None,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target=_VALID_REDIRECT,
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 503

    @pytest.mark.anyio
    async def test_session_payload_too_large_raises_400(self):
        """Huge verifier makes the session payload exceed 4096 bytes."""
        huge_verifier = "v" * 4000
        with (
            patch("auth_user_service.routes.oauth_login.settings", _login_settings()),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthController.get_google_login_url",
                return_value=("https://auth.url", "state-1", huge_verifier),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await get_google_login_url(
                    redirect_target=_VALID_REDIRECT,
                    code_challenge=_VALID_CODE_CHALLENGE,
                )
        assert exc.value.status_code == 400
        assert "too large" in exc.value.detail

    @pytest.mark.anyio
    async def test_success_returns_google_url(self):
        mock_redis = MagicMock()
        with (
            patch("auth_user_service.routes.oauth_login.settings", _login_settings()),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=mock_redis,
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthController.get_google_login_url",
                return_value=(
                    "https://accounts.google.com/o/oauth2/v2/auth?foo=bar",
                    "state-1",
                    "verifier-1",
                ),
            ),
        ):
            result = await get_google_login_url(
                redirect_target=_VALID_REDIRECT,
                code_challenge=_VALID_CODE_CHALLENGE,
            )
        assert result == {"url": "https://accounts.google.com/o/oauth2/v2/auth?foo=bar"}
        mock_redis.setex.assert_called_once()

    @pytest.mark.anyio
    async def test_success_with_prefix_allowlist_matching(self):
        """A matching prefix allowlist entry must not block the request."""
        s = _login_settings(
            OAUTH_ALLOWED_REDIRECT_PREFIXES=[
                "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef/"
            ]
        )
        with (
            patch("auth_user_service.routes.oauth_login.settings", s),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthController.get_google_login_url",
                return_value=("https://accounts.google.com/auth", "state-2", "v2"),
            ),
        ):
            result = await get_google_login_url(
                redirect_target=_VALID_REDIRECT,
                code_challenge=_VALID_CODE_CHALLENGE,
            )
        assert "url" in result


# ---------------------------------------------------------------------------
# exchange_auth_code
# ---------------------------------------------------------------------------


class TestExchangeAuthCode:
    @pytest.mark.anyio
    async def test_redis_unavailable_raises_503_and_emits_metric(self):
        """client=None branch and redis-unavailable branch covered together."""
        mock_metrics = MagicMock()
        req = MagicMock()
        req.client = None  # → client_ip = "unknown"
        req.headers.get.return_value = ""
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=None,
            ),
            patch(
                "auth_user_service.routes.oauth_login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(req, body)
        assert exc.value.status_code == 503
        mock_metrics.auth_code_exchange_total.labels(
            result="redis_unavailable"
        ).inc.assert_called_once()

    @pytest.mark.anyio
    async def test_rate_limited_raises_429(self):
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(allowed=False),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(), body)
        assert exc.value.status_code == 429

    @pytest.mark.anyio
    async def test_invalid_verifier_format_raises_400(self):
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier="short")
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(), body)
        assert exc.value.status_code == 400
        assert "verifier" in exc.value.detail

    @pytest.mark.anyio
    async def test_invalid_uuid_code_raises_400_with_metric(self):
        mock_metrics = MagicMock()
        body = ExchangeRequest(code="not-a-uuid", code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(), body)
        assert exc.value.status_code == 400
        mock_metrics.auth_code_exchange_total.labels(
            result="expired_or_invalid"
        ).inc.assert_called_once()

    @pytest.mark.anyio
    async def test_mismatched_origin_raises_400(self):
        """Configured CORS scheme + non-matching origin → 400."""
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = None
        s = _exchange_settings(CORS_ALLOWED_ORIGIN_SCHEMES=["chrome-extension://"])
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch("auth_user_service.routes.oauth_login.settings", s),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(origin="https://evil.com"), body)
        assert exc.value.status_code == 400
        assert "Origin" in exc.value.detail

    @pytest.mark.anyio
    async def test_cors_regex_none_skips_origin_check(self):
        """Unsupported CORS scheme → cors_regex is None → check skipped, flow continues."""
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = None
        # "unsupported://" is not chrome-extension:// → _build_cors_origin_regex returns None
        s = _exchange_settings(CORS_ALLOWED_ORIGIN_SCHEMES=["unsupported://"])
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch("auth_user_service.routes.oauth_login.settings", s),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(
                    _mock_request(origin="unsupported://host"), body
                )
        # CORS check skipped → falls through to pop → 400 expired (not 400 origin)
        assert exc.value.status_code == 400
        assert "Origin" not in exc.value.detail

    @pytest.mark.anyio
    async def test_matching_origin_passes_cors_check(self):
        """Valid extension origin with matching CORS scheme → passes origin check."""
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = None
        s = _exchange_settings(CORS_ALLOWED_ORIGIN_SCHEMES=["chrome-extension://"])
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        valid_origin = "chrome-extension://" + "a" * 32
        with (
            patch("auth_user_service.routes.oauth_login.settings", s),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(origin=valid_origin), body)
        # Origin passes → fails at pop (expired code)
        assert exc.value.status_code == 400
        assert "Origin" not in exc.value.detail

    @pytest.mark.anyio
    async def test_no_origin_skips_cors_check(self):
        """Empty origin header → CORS check condition is False → skipped."""
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = None
        s = _exchange_settings(CORS_ALLOWED_ORIGIN_SCHEMES=["chrome-extension://"])
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch("auth_user_service.routes.oauth_login.settings", s),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(origin=""), body)
        assert exc.value.status_code == 400
        assert "Origin" not in exc.value.detail

    @pytest.mark.anyio
    async def test_expired_code_raises_400_with_metric(self):
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = None
        mock_metrics = MagicMock()
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
            patch(
                "auth_user_service.routes.oauth_login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(), body)
        assert exc.value.status_code == 400
        mock_metrics.auth_code_exchange_total.labels(
            result="expired_or_invalid"
        ).inc.assert_called()

    @pytest.mark.anyio
    async def test_oversized_payload_raises_400_with_metric(self):
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = "x" * 8193  # > _AUTH_CODE_PAYLOAD_MAX
        mock_metrics = MagicMock()
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
            patch(
                "auth_user_service.routes.oauth_login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(), body)
        assert exc.value.status_code == 400
        mock_metrics.auth_code_exchange_total.labels(
            result="expired_or_invalid"
        ).inc.assert_called()

    @pytest.mark.anyio
    async def test_pkce_failure_raises_400_with_metric(self):
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = _valid_exchange_payload(
            challenge="W" * 43  # wrong challenge — won't match _VALID_VERIFIER
        )
        mock_metrics = MagicMock()
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
            patch(
                "auth_user_service.routes.oauth_login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            with pytest.raises(HTTPException) as exc:
                await exchange_auth_code(_mock_request(), body)
        assert exc.value.status_code == 400
        assert "PKCE" in exc.value.detail
        mock_metrics.auth_code_exchange_total.labels(
            result="pkce_failed"
        ).inc.assert_called_once()

    @pytest.mark.anyio
    async def test_success_excludes_code_challenge_from_response(self):
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = _valid_exchange_payload()
        mock_metrics = MagicMock()
        body = ExchangeRequest(code=str(_uuid.uuid4()), code_verifier=_VALID_VERIFIER)
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
            patch(
                "auth_user_service.routes.oauth_login._get_metrics",
                return_value=mock_metrics,
            ),
        ):
            result = await exchange_auth_code(_mock_request(), body)
        assert "code_challenge" not in result
        assert result["access_token"] == "tok-123"
        mock_metrics.auth_code_exchange_total.labels(
            result="success"
        ).inc.assert_called_once()

    @pytest.mark.anyio
    async def test_success_with_client_hint_logs_and_returns(self):
        """client_hint present → debug-logged; result unchanged."""
        mock_auth_code = MagicMock()
        mock_auth_code.pop.return_value = _valid_exchange_payload()
        body = ExchangeRequest(
            code=str(_uuid.uuid4()),
            code_verifier=_VALID_VERIFIER,
            client_hint="my-ext-v1",
        )
        with (
            patch(
                "auth_user_service.routes.oauth_login.settings",
                _exchange_settings(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.get_redis_client",
                return_value=MagicMock(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.ExchangeRateLimiter",
                return_value=_mock_rate_limiter(),
            ),
            patch(
                "auth_user_service.routes.oauth_login.AuthCodeStore",
                return_value=mock_auth_code,
            ),
        ):
            result = await exchange_auth_code(_mock_request(), body)
        assert "access_token" in result
        assert "code_challenge" not in result
