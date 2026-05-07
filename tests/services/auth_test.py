"""Unit tests for services.auth.AuthController."""
import base64
import hashlib
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

import auth_user_service.services.auth as _auth_module
from auth_user_service.services.auth import AuthController


class TestGenerateCodeVerifier:
    def test_returns_string(self):
        verifier = AuthController.generate_code_verifier()
        assert isinstance(verifier, str)

    def test_is_url_safe_base64_without_padding(self):
        verifier = AuthController.generate_code_verifier()
        assert "=" not in verifier
        assert "+" not in verifier
        assert "/" not in verifier

    def test_length_is_43_chars(self):
        # 32 bytes → 43 chars of base64url without padding
        verifier = AuthController.generate_code_verifier()
        assert len(verifier) == 43

    def test_each_call_produces_unique_value(self):
        v1 = AuthController.generate_code_verifier()
        v2 = AuthController.generate_code_verifier()
        assert v1 != v2


class TestGenerateCodeChallenge:
    def test_is_sha256_of_verifier_base64url(self):
        verifier = "testverifier123"
        expected_digest = hashlib.sha256(verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(expected_digest).decode().rstrip("=")

        result = AuthController.generate_code_challenge(verifier)

        assert result == expected

    def test_no_padding(self):
        verifier = AuthController.generate_code_verifier()
        challenge = AuthController.generate_code_challenge(verifier)
        assert "=" not in challenge

    def test_challenge_differs_from_verifier(self):
        verifier = AuthController.generate_code_verifier()
        challenge = AuthController.generate_code_challenge(verifier)
        assert challenge != verifier

    def test_deterministic_for_same_input(self):
        verifier = "fixed_test_verifier"
        c1 = AuthController.generate_code_challenge(verifier)
        c2 = AuthController.generate_code_challenge(verifier)
        assert c1 == c2


class TestCreateState:
    def test_returns_string(self):
        state = AuthController.create_state()
        assert isinstance(state, str)

    def test_sufficient_length(self):
        state = AuthController.create_state()
        assert len(state) >= 16

    def test_each_call_is_unique(self):
        s1 = AuthController.create_state()
        s2 = AuthController.create_state()
        assert s1 != s2


class TestGetGoogleLoginUrl:
    def test_returns_google_oauth_url(self):
        with patch("auth_user_service.services.auth.get_redis_client") as mock_get_redis, \
             patch("auth_user_service.services.auth.PKCEStore") as mock_pkce_cls:
            mock_pkce = MagicMock()
            mock_pkce_cls.return_value = mock_pkce

            url = AuthController.get_google_login_url("http://localhost/callback")

        assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        assert "response_type=code" in url
        assert "code_challenge_method=S256" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url

    def test_stores_pkce_verifier(self):
        with patch("auth_user_service.services.auth.get_redis_client"), \
             patch("auth_user_service.services.auth.PKCEStore") as mock_pkce_cls:
            mock_pkce = MagicMock()
            mock_pkce_cls.return_value = mock_pkce

            AuthController.get_google_login_url("http://localhost/callback")

        mock_pkce.store.assert_called_once()
        state_arg, verifier_arg = mock_pkce.store.call_args[0]
        assert isinstance(state_arg, str)
        assert isinstance(verifier_arg, str)

    def test_url_without_redirect_uri(self):
        with patch("auth_user_service.services.auth.get_redis_client"), \
             patch("auth_user_service.services.auth.PKCEStore") as mock_pkce_cls:
            mock_pkce_cls.return_value = MagicMock()
            url = AuthController.get_google_login_url()

        assert "https://accounts.google.com/o/oauth2/v2/auth?" in url


class TestAuthenticate:
    def test_valid_credentials_returns_user(self, db_session, sample_user):
        from tests.conftest import TEST_PASSWORD

        result = AuthController.authenticate(
            session=db_session,
            email=sample_user.email,
            password=TEST_PASSWORD,
        )

        assert result is not None
        assert str(result.id) == str(sample_user.id)

    def test_wrong_password_returns_none(self, db_session, sample_user):
        result = AuthController.authenticate(
            session=db_session,
            email=sample_user.email,
            password="wrongpassword",
        )

        assert result is None

    def test_unknown_email_returns_none(self, db_session):
        result = AuthController.authenticate(
            session=db_session,
            email="nobody@example.com",
            password="anypassword",
        )

        assert result is None


class TestGetTokensExpire:
    def test_returns_two_timedeltas(self):
        access_delta, refresh_delta = AuthController.get_tokens_expire()

        assert isinstance(access_delta, timedelta)
        assert isinstance(refresh_delta, timedelta)

    def test_access_token_expires_before_refresh(self):
        access_delta, refresh_delta = AuthController.get_tokens_expire()
        assert access_delta < refresh_delta


class TestCreateAuthTokens:
    def test_returns_three_strings(self):
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.full_name = "Test User"
        user.email = "test@example.com"
        user.avatar = None
        user.is_active = True
        user.email_verified = True
        user.is_superuser = False
        user.role = "user"

        access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)

        assert isinstance(access_token, str)
        assert isinstance(refresh_token, str)
        assert isinstance(jti, str)
        assert uuid.UUID(jti)

    def test_jti_is_valid_uuid(self):
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.full_name = "User"
        user.email = "u@example.com"
        user.avatar = None
        user.is_active = True
        user.email_verified = True
        user.is_superuser = False
        user.role = "user"

        _, _, jti = AuthController.create_auth_tokens(user=user)

        uuid.UUID(jti)  # raises ValueError if not a valid UUID

    def test_rs256_missing_private_key_raises(self):
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.full_name = "User"
        user.email = "u@example.com"
        user.avatar = None
        user.is_active = True
        user.email_verified = True
        user.is_superuser = False
        user.role = "user"

        with patch("auth_user_service.services.auth.settings") as mock_cfg:
            mock_cfg.ACCESS_TOKEN_ALGORITHM = "RS256"
            mock_cfg.ACCESS_PRIVATE_KEY = None
            mock_cfg.ACCESS_TOKEN_EXPIRE_MINUTES = 30
            mock_cfg.REFRESH_TOKEN_EXPIRE_MINUTES = 120
            with pytest.raises(ValueError, match="ACCESS_PRIVATE_KEY"):
                AuthController.create_auth_tokens(user=user)

    def test_rs256_with_private_key_creates_tokens(self):
        user = MagicMock()
        user.id = str(uuid.uuid4())
        user.full_name = "User"
        user.email = "u@example.com"
        user.avatar = None
        user.is_active = True
        user.email_verified = True
        user.is_superuser = False
        user.role = "user"

        fake_jti = str(uuid.uuid4())
        fake_priv = SecretStr("-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----")
        fake_refresh = SecretStr("Zz1_fake-refresh-secret-long-enough-12345678")

        with patch("auth_user_service.services.auth.settings") as mock_cfg, \
             patch.object(_auth_module.SecurityHelper, "create_access_token",
                          return_value=("acc_tok", fake_jti)), \
             patch.object(_auth_module.SecurityHelper, "create_refresh_token",
                          return_value=("ref_tok", fake_jti)):
            mock_cfg.ACCESS_TOKEN_ALGORITHM = "RS256"
            mock_cfg.ACCESS_PRIVATE_KEY = fake_priv
            mock_cfg.ACCESS_TOKEN_EXPIRE_MINUTES = 30
            mock_cfg.REFRESH_TOKEN_EXPIRE_MINUTES = 120
            mock_cfg.REFRESH_SECRET_KEY = fake_refresh
            mock_cfg.REFRESH_TOKEN_ALGORITHM = "HS256"
            access, refresh, jti = AuthController.create_auth_tokens(user=user)

        assert access == "acc_tok"
        assert refresh == "ref_tok"
        assert jti == fake_jti


class TestCreateAuthSession:
    def test_creates_new_session(self, db_session, sample_user):
        _, refresh_token, jti = AuthController.create_auth_tokens(user=sample_user)

        session_item = AuthController.create_auth_session(
            session=db_session,
            user=sample_user,
            jti=jti,
            refresh_token=refresh_token,
        )

        assert session_item is not None
        assert session_item.jwt_jti == jti

    def test_creates_session_with_external_tokens(self, db_session, sample_user):
        from pydantic import SecretStr
        from auth_sdk_m8.schemas.auth import ExternalTokensData

        _, refresh_token, jti = AuthController.create_auth_tokens(user=sample_user)

        ext = ExternalTokensData(
            access=SecretStr("ext_access_token"),
            refresh=SecretStr("ext_refresh_token"),
            expires=3600,
        )

        session_item = AuthController.create_auth_session(
            session=db_session,
            user=sample_user,
            jti=jti + "_ext",
            refresh_token=refresh_token,
            external_token=ext,
        )

        assert session_item.external_access_token is not None
        assert session_item.external_refresh_token is not None
        assert session_item.external_token_expires_at is not None
