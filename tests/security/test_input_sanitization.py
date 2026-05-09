"""Security regression: timing attack prevention and Redis key sanitization.

Verifies that:
- bcrypt always runs regardless of whether the email exists (timing-safe)
- Unknown emails use _DUMMY_HASH so response time is constant
- Known emails use the stored hash
- CRLF / NUL / control chars are stripped from Redis login-rate-limit keys
- Extremely long emails are capped before use as a Redis key
- Normal email addresses pass through unchanged
"""

from unittest.mock import MagicMock, patch

from auth_user_service.core.client import LoginRateLimiter
from auth_user_service.core.security import SecurityHelper
from auth_user_service.services.auth import AuthController, _DUMMY_HASH


class TestTimingAttackPrevention:
    """bcrypt must run for every login attempt, including non-existent users."""

    def test_dummy_hash_is_a_valid_bcrypt_string(self):
        """Sentinel hash must be a real bcrypt hash so the cost is identical."""
        assert _DUMMY_HASH.startswith("$2b$")
        assert len(_DUMMY_HASH) >= 60

    def test_unknown_email_still_calls_verify_password(self, db_session):
        """verify_password must be called even when the email is not in the DB."""
        with patch.object(
            SecurityHelper, "verify_password", return_value=False
        ) as mock_verify:
            AuthController.authenticate(
                session=db_session,
                email="ghost@example.com",
                password="anypassword",
            )
        mock_verify.assert_called_once()

    def test_unknown_email_passes_dummy_hash_to_verify(self, db_session):
        """When the user does not exist, _DUMMY_HASH must be the hash argument."""
        with patch.object(
            SecurityHelper, "verify_password", return_value=False
        ) as mock_verify:
            AuthController.authenticate(
                session=db_session,
                email="ghost@example.com",
                password="anypassword",
            )
        _, hash_arg = mock_verify.call_args[0]
        assert hash_arg == _DUMMY_HASH

    def test_known_email_passes_real_hash_to_verify(self, db_session, sample_user):
        """When the user exists, the stored hashed_password must be used."""
        with patch.object(
            SecurityHelper, "verify_password", return_value=True
        ) as mock_verify:
            AuthController.authenticate(
                session=db_session,
                email=sample_user.email,
                password="anypassword",
            )
        _, hash_arg = mock_verify.call_args[0]
        assert hash_arg == sample_user.hashed_password
        assert hash_arg != _DUMMY_HASH

    def test_unknown_email_returns_none(self, db_session):
        result = AuthController.authenticate(
            session=db_session,
            email="nobody@example.com",
            password="somepassword",
        )
        assert result is None

    def test_wrong_password_for_known_user_returns_none(self, db_session, sample_user):
        result = AuthController.authenticate(
            session=db_session,
            email=sample_user.email,
            password="completely_wrong_password",
        )
        assert result is None


class TestLoginRateLimiterKeySanitization:
    """User-supplied email must be sanitised before use as a Redis key suffix."""

    def setup_method(self):
        self.mock_redis = MagicMock()
        self.limiter = LoginRateLimiter(self.mock_redis)

    def test_normal_email_passes_through_unchanged(self):
        key = self.limiter._key("user@example.com")
        assert key == "login:attempts:user@example.com"

    def test_crlf_stripped_from_key(self):
        # The security threat is the CRLF itself creating a binary key that escapes
        # the login:attempts: namespace — the printable text after \r\n is harmless.
        key = self.limiter._key("user@example.com\r\nX-Header:value")
        assert "\r" not in key
        assert "\n" not in key

    def test_carriage_return_alone_stripped(self):
        key = self.limiter._key("user@example.com\revil")
        assert "\r" not in key

    def test_newline_alone_stripped(self):
        key = self.limiter._key("user@example.com\nevil")
        assert "\n" not in key

    def test_null_byte_stripped(self):
        key = self.limiter._key("user@example.com\x00injected")
        assert "\x00" not in key

    def test_all_ascii_control_chars_stripped(self):
        malicious = "user@example.com" + "".join(chr(i) for i in range(32))
        key = self.limiter._key(malicious)
        suffix = key[len(LoginRateLimiter.PREFIX) :]
        for ch in suffix:
            assert ch.isprintable(), f"Non-printable char {repr(ch)} found in Redis key"

    def test_very_long_email_capped_at_max_id_len(self):
        long_email = "a" * 1000 + "@example.com"
        key = self.limiter._key(long_email)
        suffix = key[len(LoginRateLimiter.PREFIX) :]
        assert len(suffix) <= LoginRateLimiter.MAX_ID_LEN

    def test_key_length_cap_constant_defined(self):
        assert LoginRateLimiter.MAX_ID_LEN == 255

    def test_unicode_printable_preserved(self):
        """Printable non-ASCII characters should not be stripped."""
        key = self.limiter._key("üser@example.com")
        assert "üser@example.com" in key

    def test_key_always_starts_with_prefix(self):
        for email in [
            "normal@example.com",
            "evil\r\n@example.com",
            "\x00\x01\x02",
        ]:
            key = self.limiter._key(email)
            assert key.startswith(LoginRateLimiter.PREFIX)
