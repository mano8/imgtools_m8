"""Security regression: JWT validation rejects abused tokens and enforces revocation.

Verifies that:
- Completely invalid / empty tokens return 403
- Tampered signatures return 403
- Tokens signed with the wrong secret return 403
- Inactive-user tokens return 403
- Blacklisted JTIs return 401 in stateful mode
- Blacklist check is skipped in hybrid and stateless modes
- Redis being down in stateful mode is fail-open (token accepted, not 500)
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from auth_sdk_m8.schemas.auth import TokenAccessData, TokenSecret
from auth_sdk_m8.schemas.user import UserModel
from auth_user_service.core.deps import get_current_user
from auth_user_service.core.security import SecurityHelper


def _make_token(
    email: str = "sec_test@example.com",
    is_active: bool = True,
    is_superuser: bool = False,
    expires: timedelta = timedelta(minutes=30),
    secret_override: str = None,
) -> str:
    """Create a signed access token using real signing machinery."""
    from auth_user_service.core.config import settings

    if secret_override is not None:
        secret = TokenSecret(
            secret_key=SecretStr(secret_override),
            algorithm=settings.ACCESS_TOKEN_ALGORITHM,
        )
    else:
        secret = TokenSecret(
            secret_key=settings.ACCESS_SECRET_KEY,
            algorithm=settings.ACCESS_TOKEN_ALGORITHM,
        )
    data = TokenAccessData(
        sub=str(uuid.uuid4()),
        role="user",
        email=email,
        full_name="Security Test User",
        is_superuser=is_superuser,
        is_active=is_active,
    )
    token, _ = SecurityHelper.create_access_token(
        data=data,
        expires_delta=expires,
        secrets=secret,
    )
    return token


class TestJWTAbuse:
    """Malformed or forged tokens must be rejected before any Redis/DB check."""

    def test_random_string_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="notajwtatall")
        assert exc_info.value.status_code == 403

    def test_empty_string_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="")
        assert exc_info.value.status_code == 403

    def test_two_part_jwt_raises_403(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="header.payload")
        assert exc_info.value.status_code == 403

    def test_tampered_signature_raises_403(self):
        token = _make_token()
        header, payload, sig = token.split(".")
        # Flip the last four characters of the signature
        tampered_sig = sig[:-4] + ("AAAA" if sig[-4:] != "AAAA" else "BBBB")
        tampered = f"{header}.{payload}.{tampered_sig}"
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=tampered)
        assert exc_info.value.status_code == 403

    def test_wrong_secret_raises_403(self):
        """Token signed with a different secret must be rejected."""
        token = _make_token(
            secret_override="Zz1_completely-different-secret-key-1234567890"
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=token)
        assert exc_info.value.status_code == 403

    def test_inactive_user_token_raises_403(self):
        token = _make_token(is_active=False)
        mock_redis = MagicMock()
        with (
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=mock_redis
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_mgr,
        ):
            mock_mgr.return_value.is_blacklisted.return_value = False
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token)
        assert exc_info.value.status_code == 403
        assert (
            "Inactive" in exc_info.value.detail or "inactive" in exc_info.value.detail
        )


class TestJWTRevocation:
    """Stateful mode must check the Redis blacklist; other modes must not."""

    def test_blacklisted_jti_raises_401_stateful(self):
        token = _make_token()
        mock_redis = MagicMock()
        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=mock_redis
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_mgr,
        ):
            mock_cfg.TOKEN_MODE = "stateful"
            mock_mgr.return_value.is_blacklisted.return_value = True
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=token)
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()

    def test_valid_jti_passes_blacklist_check_stateful(self):
        token = _make_token()
        mock_redis = MagicMock()
        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch(
                "auth_user_service.core.deps.get_redis_client", return_value=mock_redis
            ),
            patch("auth_user_service.core.deps.RedisSessionManager") as mock_mgr,
        ):
            mock_cfg.TOKEN_MODE = "stateful"
            mock_mgr.return_value.is_blacklisted.return_value = False
            result = get_current_user(token=token)
        assert isinstance(result, UserModel)

    def test_blacklist_not_checked_in_hybrid_mode(self):
        token = _make_token()
        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client") as mock_get_redis,
        ):
            mock_cfg.TOKEN_MODE = "hybrid"
            mock_cfg.is_stateful = False
            get_current_user(token=token)
        mock_get_redis.assert_not_called()

    def test_blacklist_not_checked_in_stateless_mode(self):
        token = _make_token()
        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client") as mock_get_redis,
        ):
            mock_cfg.TOKEN_MODE = "stateless"
            mock_cfg.is_stateful = False
            get_current_user(token=token)
        mock_get_redis.assert_not_called()


class TestRedisDownFailOpen:
    """Redis unavailable in stateful mode → blacklist check skipped → token accepted."""

    def test_redis_none_allows_valid_token_stateful(self):
        """Fail-open: when Redis is down, we cannot revoke but must not crash."""
        token = _make_token()
        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client", return_value=None),
        ):
            mock_cfg.TOKEN_MODE = "stateful"
            result = get_current_user(token=token)
        assert isinstance(result, UserModel)

    def test_redis_none_does_not_raise_500(self):
        """Redis being None must produce at most an access decision — never a crash."""
        token = _make_token()
        with (
            patch("auth_user_service.core.deps.settings") as mock_cfg,
            patch("auth_user_service.core.deps.get_redis_client", return_value=None),
        ):
            mock_cfg.TOKEN_MODE = "stateful"
            try:
                get_current_user(token=token)
            except HTTPException as ex:
                assert ex.status_code != 500
