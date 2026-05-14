"""
Unit tests for SecurityHelper class.

This module tests the functionality of the SecurityHelper class, including
token creation, password hashing, and validation.
"""

import secrets
import uuid
from datetime import timedelta
import bcrypt
import jwt

from pydantic import SecretStr, ValidationError
import pytest
from auth_user_service.core.security import SecurityHelper
from auth_sdk_m8.schemas.auth import TokenAccessData, TokenMinimalData, TokenSecret


class TestSecurityHelper:
    """
    Unit tests for the SecurityHelper class.
    """

    @pytest.fixture
    def token_secrets_fixture(self):
        """Fixture for providing token secrets."""
        # Must satisfy SECRET_KEY_REGEX: [A-Za-z\d\-_]{32,} with lower+upper+digit+[-_]
        import re

        _pattern = re.compile(
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[-_])[A-Za-z\d\-_]{32,}$"
        )
        key = secrets.token_urlsafe(32)
        while not _pattern.match(key):
            key = secrets.token_urlsafe(32)
        return TokenSecret(secret_key=SecretStr(key), algorithm="HS256")

    @pytest.fixture
    def access_data(self):
        """Fixture for providing complete access token data."""
        return TokenAccessData(
            sub=str(uuid.uuid4()),
            role="admin",
            email="test_user@example.com",
            full_name="Test User",
            is_superuser=False,
        )

    @pytest.fixture
    def minimal_data(self):
        """Fixture for providing minimal token data."""
        return TokenMinimalData(sub=str(uuid.uuid4()))

    def test_create_access_token(self, access_data, token_secrets_fixture):
        """
        Test the creation of an access token and validate its structure and content.

        Args:
            access_data (TokenAccessData): Access token data.
            token_secrets_fixture (TokenSecret): Token token_secrets_fixture.
        """
        expires_delta = timedelta(minutes=15)
        token, jti = SecurityHelper.create_access_token(
            access_data, expires_delta, token_secrets_fixture
        )

        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert uuid.UUID(jti)  # Validate JTI is a valid UUID

        decoded_token = jwt.decode(
            token,
            token_secrets_fixture.secret_key.get_secret_value(),
            algorithms=[token_secrets_fixture.algorithm],
        )
        assert decoded_token["sub"] == access_data.sub
        assert decoded_token["role"] == access_data.role
        assert decoded_token["email"] == access_data.email
        assert decoded_token["full_name"] == access_data.full_name
        assert decoded_token["is_superuser"] == access_data.is_superuser
        assert decoded_token["type"] == "access"
        assert "exp" in decoded_token
        assert "jti" in decoded_token

    def test_create_refresh_token(self, minimal_data, token_secrets_fixture):
        """
        Test the creation of a refresh token and validate its structure and content.

        Args:
            minimal_data (TokenMinimalData): Minimal token data.
            token_secrets_fixture (TokenSecret): Token token_secrets_fixture.
        """
        expires_delta = timedelta(days=7)
        token, jti = SecurityHelper.create_refresh_token(
            minimal_data, expires_delta, token_secrets_fixture
        )

        assert isinstance(token, str)
        assert isinstance(jti, str)
        assert uuid.UUID(jti)  # Validate JTI is a valid UUID

        decoded_token = jwt.decode(
            token,
            token_secrets_fixture.secret_key.get_secret_value(),
            algorithms=[token_secrets_fixture.algorithm],
        )
        assert decoded_token["sub"] == minimal_data.sub
        assert decoded_token["type"] == "refresh"
        assert "exp" in decoded_token
        assert "jti" in decoded_token

    def test_create_refresh_token_with_custom_jti(
        self, minimal_data, token_secrets_fixture
    ):
        """
        Test the creation of a refresh token with a custom JTI.

        Args:
            minimal_data (TokenMinimalData): Minimal token data.
            token_secrets_fixture (TokenSecret): Token token_secrets_fixture.
            custom_jti (str): Custom JTI value.
        """
        custom_jti = str(uuid.uuid4())
        expires_delta = timedelta(days=7)
        token, jti = SecurityHelper.create_refresh_token(
            minimal_data, expires_delta, token_secrets_fixture, jti=custom_jti
        )

        assert jti == custom_jti

        decoded_token = jwt.decode(
            token,
            token_secrets_fixture.secret_key.get_secret_value(),
            algorithms=[token_secrets_fixture.algorithm],
        )
        assert decoded_token["jti"] == custom_jti

    @staticmethod
    @pytest.mark.parametrize(
        "plain_password, hashed_password, expected_result",
        [
            (
                "secure_password",
                bcrypt.hashpw(
                    "secure_password".encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8"),
                True,
            ),
            (
                "wrong_password",
                bcrypt.hashpw(
                    "secure_password".encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8"),
                False,
            ),
        ],
        ids=["correct_password_matches", "wrong_password_no_match"],
    )
    def test_verify_password(plain_password, hashed_password, expected_result):
        """
        Test password verification.

        Args:
            plain_password (str): Plain text password.
            hashed_password (str): Hashed password.
            expected_result (bool): Expected verification result.
        """
        assert (
            SecurityHelper.verify_password(plain_password, hashed_password)
            is expected_result
        )

    @staticmethod
    def test_verify_password_invalid_hash():
        """
        Test password verification with an invalid hash.
        """
        plain_password = "secure_password"
        invalid_hashed_password = "invalid_hash"

        assert (
            SecurityHelper.verify_password(plain_password, invalid_hashed_password)
            is False
        )

    def test_get_password_hash(self):
        """
        Test password hashing and ensure it matches bcrypt standards.
        """
        password = "secure_password"
        hashed_password = SecurityHelper.get_password_hash(password)

        assert isinstance(hashed_password, str)
        assert bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))

    @pytest.mark.parametrize(
        "secret_key, expected_exception",
        [
            (SecretStr(""), ValidationError),
            (SecretStr("sdfsdfJKKJSHD_sdf4564sd5f46_QDQSDQS4654!"), ValidationError),
        ],
    )
    def test_create_access_token_with_invalid_secret(
        self, access_data, secret_key, expected_exception
    ):
        """
        Test access token creation with invalid token_secrets_fixture.

        Args:
            access_data (TokenAccessData): Access token data.
            secret_key (str): Invalid secret key.
            expected_exception (Exception): Expected exception type.
        """
        expires_delta = timedelta(minutes=15)

        with pytest.raises(expected_exception):
            token_secret = TokenSecret(secret_key=secret_key, algorithm="HS256")
            SecurityHelper.create_access_token(access_data, expires_delta, token_secret)

    @pytest.mark.parametrize(
        "secret_key, expected_exception",
        [
            (SecretStr(""), ValidationError),
            (SecretStr("sdfsdfJKKJSHD_sdf4564sd5f46_QDQSDQS4654!"), ValidationError),
        ],
    )
    def test_create_refresh_token_with_invalid_secret(
        self, minimal_data, secret_key, expected_exception
    ):
        """
        Test refresh token creation with invalid token_secrets_fixture.

        Args:
            minimal_data (TokenMinimalData): Minimal token data.
            secret_key (str): Invalid secret key.
            expected_exception (Exception): Expected exception type.
        """
        expires_delta = timedelta(days=7)
        with pytest.raises(expected_exception):
            token_secret = TokenSecret(secret_key=secret_key, algorithm="HS256")
            SecurityHelper.create_refresh_token(
                minimal_data, expires_delta, token_secret
            )

    def test_encrypt_and_decrypt_token_roundtrip(self):
        """Encrypting then decrypting returns the original plaintext."""
        plaintext = "my_secret_access_token"
        key = "a_strong_32byte_encryption_key!!"

        encrypted = SecurityHelper.encrypt_token(plaintext, key)
        decrypted = SecurityHelper.decrypt_token(encrypted, key)

        assert decrypted == plaintext
        assert encrypted != plaintext

    def test_encrypt_produces_different_ciphertexts(self):
        """Fernet produces unique ciphertexts even for the same plaintext."""
        key = "a_strong_32byte_encryption_key!!"
        token = "same_token"

        enc1 = SecurityHelper.encrypt_token(token, key)
        enc2 = SecurityHelper.encrypt_token(token, key)

        assert enc1 != enc2  # Fernet uses random IV

    def test_decrypt_with_wrong_key_raises(self):
        """Decrypting with a different key should raise an exception."""

        key1 = "a_strong_32byte_encryption_key!!"
        key2 = "different_32byte_encryption_key!"
        token = "some_token_value"

        encrypted = SecurityHelper.encrypt_token(token, key1)

        with pytest.raises(Exception):
            SecurityHelper.decrypt_token(encrypted, key2)

    def test_fernet_deterministic_for_same_key(self):
        """The same key always produces the same Fernet instance behaviour."""
        key = "consistent_key_string"
        f1 = SecurityHelper._fernet(key)
        f2 = SecurityHelper._fernet(key)

        sample = b"hello"
        enc = f1.encrypt(sample)
        dec = f2.decrypt(enc)
        assert dec == sample
