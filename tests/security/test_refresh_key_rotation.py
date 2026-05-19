"""Unit tests for REFRESH_SECRET_KEY_OLD key rotation fallback.

Verifies that SecurityHelper.decode_refresh_token (inherited from
ComSecurityHelper) correctly falls back to old_secrets when the current
key fails with a signature error, and that the expiry fast-path is never
bypassed by the fallback.

These tests exercise the path wired in login.py:
    SecurityHelper.decode_refresh_token(
        refresh_token,
        secrets=_REFRESH_SECRETS,
        return_jti=True,
        old_secrets=_REFRESH_OLD_SECRETS,   # None when not rotating
    )
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import SecretStr

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.auth import TokenSecret
from auth_user_service.core.security import SecurityHelper

# Keys satisfy SECRET_KEY_REGEX: 32+ chars, mixed-case, digit, hyphen/underscore.
_CURRENT_KEY = "Abcdef-1234_XYZ-abcdef-ghijkl-mnopqr-stuvwx"
_OLD_KEY = "Zyxwvu-9876_ABC-zyxwvu-tsrqpo-nmlkji-hgfedc"
_UNKNOWN_KEY = "Qwerty1-2345_ZZZ-qwerty1-234567-890abc-defghi"

_CURRENT = TokenSecret(secret_key=SecretStr(_CURRENT_KEY), algorithm="HS256")
_OLD = TokenSecret(secret_key=SecretStr(_OLD_KEY), algorithm="HS256")


def _make_refresh_token(secret: str, exp_offset_hours: int = 1, **extra) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(uuid.uuid4()),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": int((now + timedelta(hours=exp_offset_hours)).timestamp()),
        **extra,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class TestRefreshKeyRotationFallback:
    """old_secrets fallback: old-key tokens accepted during rotation window."""

    def test_current_key_token_accepted_without_old_secrets(self):
        token = _make_refresh_token(_CURRENT_KEY)
        user_id, jti = SecurityHelper.decode_refresh_token(
            token, _CURRENT, return_jti=True
        )
        assert isinstance(user_id, uuid.UUID)
        assert isinstance(jti, str) and jti

    def test_old_key_token_accepted_with_old_secrets(self):
        """Token signed with old key must succeed when old_secrets is provided."""
        token = _make_refresh_token(_OLD_KEY)
        user_id, jti = SecurityHelper.decode_refresh_token(
            token, _CURRENT, return_jti=True, old_secrets=_OLD
        )
        assert isinstance(user_id, uuid.UUID)
        assert isinstance(jti, str) and jti

    def test_old_key_token_rejected_without_old_secrets(self):
        """Without old_secrets configured, old-key tokens must be refused."""
        token = _make_refresh_token(_OLD_KEY)
        with pytest.raises(InvalidToken):
            SecurityHelper.decode_refresh_token(token, _CURRENT, return_jti=True)

    def test_expired_old_key_token_rejected_even_with_old_secrets(self):
        """Expiry is checked before the old-key fallback — never bypassed."""
        token = _make_refresh_token(_OLD_KEY, exp_offset_hours=-1)
        with pytest.raises(InvalidToken, match="expired"):
            SecurityHelper.decode_refresh_token(
                token, _CURRENT, return_jti=True, old_secrets=_OLD
            )

    def test_unknown_key_token_rejected_even_with_old_secrets(self):
        """Token from a third unknown key must fail regardless of old_secrets."""
        token = _make_refresh_token(_UNKNOWN_KEY)
        with pytest.raises(InvalidToken, match="Invalid refresh token"):
            SecurityHelper.decode_refresh_token(
                token, _CURRENT, return_jti=True, old_secrets=_OLD
            )
