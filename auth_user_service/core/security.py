"""
Module for security and authentication utilities.

This module provides functions for:
- Creating JWT access tokens with expiration.
- Creating JWT refresh tokens with unique JTI.
- Extracting the JTI from tokens.
- Hashing tokens for secure storage.
- Decoding refresh tokens (subject and JTI).
- Password hashing and verification.
"""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
import uuid

import bcrypt
import jwt
from cryptography.fernet import Fernet

from auth_sdk_m8.schemas.auth import TokenMinimalData, TokenAccessData, TokenSecret
from auth_sdk_m8.core.security import ComSecurityHelper


class SecurityHelper(ComSecurityHelper):
    """
    A helper class for security-related operations, including token creation,
    hashing, and password verification.
    """

    @staticmethod
    def create_access_token(
        data: TokenAccessData,
        expires_delta: timedelta,
        secrets: TokenSecret,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        kid: Optional[str] = None,
    ) -> Union[jwt.PyJWT, str]:
        """
        Create a JWT access token.

        Parameters:
            data (TokenAccessData):
                The payload data for the token.
            expires_delta (timedelta):
                The time duration after which the token expires.
            issuer: Optional ``iss`` claim embedded in the token.
            audience: Optional ``aud`` claim embedded in the token.
            kid: Optional key ID embedded in the JWT ``kid`` header.
                Required for JWKS-based key rotation with RS256/ES256.

        Returns:
            str:
                The encoded JWT access token as a string.
        """
        expire = datetime.now(timezone.utc) + expires_delta
        jti = str(uuid.uuid4())
        to_encode = data.model_dump()
        to_encode.update({"exp": expire, "jti": jti, "type": "access"})
        if issuer:
            to_encode["iss"] = issuer
        if audience:
            to_encode["aud"] = audience
        encoded_jwt = jwt.encode(
            to_encode,
            secrets.secret_key.get_secret_value(),
            algorithm=secrets.algorithm,
            headers={"kid": kid} if kid else None,
        )
        return encoded_jwt, jti

    @staticmethod
    def create_refresh_token(
        data: TokenMinimalData,
        expires_delta: timedelta,
        secrets: TokenSecret,
        jti: str = None,
    ) -> Union[jwt.PyJWT, str]:
        """
        Create a JWT refresh token.

        Parameters:
            subject (str | Any):
                The subject for the token, typically a user identifier.
            expires_delta (timedelta):
                The time duration after which the token expires.

        Returns:
            str:
                The encoded JWT refresh token as a string.
        """
        expire = datetime.now(timezone.utc) + expires_delta
        if jti is None:
            jti = str(uuid.uuid4())
        to_encode = data.model_dump()
        to_encode.update({"exp": expire, "jti": jti, "type": "refresh"})
        encoded_jwt = jwt.encode(
            to_encode,
            secrets.secret_key.get_secret_value(),
            algorithm=secrets.algorithm,
        )
        return encoded_jwt, jti

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain text password against a hashed password.

        Parameters:
            plain_password (str):
                The plain text password to verify.
            hashed_password (str):
                The hashed password to compare against.

        Returns:
            bool:
                True if the plain password matches the hashed password,
                False otherwise.
        """
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except ValueError:
            return False

    @staticmethod
    def _fernet(encryption_key: str) -> Fernet:
        """Derive a Fernet instance from the given key string via SHA-256."""
        raw = hashlib.sha256(encryption_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(raw))

    @staticmethod
    def encrypt_token(token: str, encryption_key: str) -> str:
        """Encrypt a plaintext token for secure storage."""
        return (
            SecurityHelper._fernet(encryption_key)
            .encrypt(token.encode("utf-8"))
            .decode("utf-8")
        )

    @staticmethod
    def decrypt_token(encrypted: str, encryption_key: str) -> str:
        """Decrypt a stored token back to plaintext."""
        return (
            SecurityHelper._fernet(encryption_key)
            .decrypt(encrypted.encode("utf-8"))
            .decode("utf-8")
        )

    @staticmethod
    def get_password_hash(password: str) -> str:
        """
        Generate a hashed password from a plain text password.

        Parameters:
            password (str):
                The plain text password to hash.

        Returns:
            str:
                The generated hashed password.
        """
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
