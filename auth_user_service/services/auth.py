"""
AuthController.py
===================
"""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional
from urllib.parse import quote_plus

from sqlmodel import Session

from auth_user_service.services.client_sessions import SessionController
from auth_user_service.services.users import UserController
from auth_user_service.db_models.users import User
from auth_user_service.db_models.sessions import ClientSessionCreate, ClientSession
from auth_user_service.core.config import settings
from auth_user_service.core.security import SecurityHelper

from fastapi import HTTPException

from auth_sdk_m8.schemas.auth import (
    ASYMMETRIC_ALGORITHMS,
    ExternalTokensData,
    TokenAccessData,
    TokenMinimalData,
    TokenSecret,
)

# Pre-computed hash used to run bcrypt for non-existent users, eliminating the
# timing difference that would otherwise reveal valid email addresses.
_DUMMY_HASH: str = SecurityHelper.get_password_hash(secrets.token_hex(32))


def _resolve_access_secret(algo: str) -> TokenSecret:
    """Return the signing secret for access tokens based on the configured algorithm."""
    if algo in ASYMMETRIC_ALGORITHMS:
        if not settings.ACCESS_PRIVATE_KEY:
            raise ValueError(
                f"ACCESS_PRIVATE_KEY (PEM) is required to sign {algo} tokens"
            )
        return TokenSecret(secret_key=settings.ACCESS_PRIVATE_KEY, algorithm=algo)
    return TokenSecret(secret_key=settings.ACCESS_SECRET_KEY, algorithm=algo)


def _resolve_kid(algo: str) -> Optional[str]:
    """Return the key ID to embed in the JWT ``kid`` header.

    Uses ``ACCESS_KEY_ID`` from settings when explicitly configured.
    For asymmetric algorithms, falls back to a stable 16-char SHA-256
    fingerprint of the public key so consumers can match keys via JWKS
    without requiring a configured key ID.
    Returns ``None`` for symmetric (HS256) algorithms — the secret must
    not be published.
    """
    if algo not in ASYMMETRIC_ALGORITHMS:
        return None
    explicit: Optional[str] = getattr(settings, "ACCESS_KEY_ID", None) or None
    if explicit:
        return explicit
    pub = settings.ACCESS_PUBLIC_KEY or ""
    return hashlib.sha256(pub.strip().encode()).hexdigest()[:16]


class AuthController:
    """
    Manages OAuth2 with PKCE for Google authorization.
    """

    @staticmethod
    def generate_code_verifier() -> str:
        """
        Generates a code_verifier for PKCE.
        """
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    @staticmethod
    def generate_code_challenge(code_verifier: str) -> str:
        """
        Generates a code_challenge from the code_verifier using SHA256.
        """
        digest = hashlib.sha256(code_verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    @staticmethod
    def create_state() -> str:
        """
        Creates a state parameter for OAuth2 authorization.
        """
        return secrets.token_urlsafe(16)

    @classmethod
    def get_google_login_url(
        cls, redirect_uri: Optional[str] = None
    ) -> tuple[str, str, str]:
        """Return (oauth_url, state, pkce_verifier) for Google OAuth2 with PKCE.

        The caller is responsible for assembling the OAuthSessionStore payload
        (which combines pkce_verifier with the client-supplied redirect_target
        and code_challenge) and storing it before redirecting the user.

        Args:
            redirect_uri: Fixed backend callback URI (from GOOGLE_OAUTH_REDIRECT_URI).
        """
        if not settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=503, detail="Google OAuth is not configured."
            )
        state = cls.create_state()
        code_verifier = cls.generate_code_verifier()
        code_challenge = cls.generate_code_challenge(code_verifier)

        params = {
            "response_type": "code",
            "client_id": settings.GOOGLE_CLIENT_ID.get_secret_value(),
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        query = "&".join(
            f"{k}={quote_plus(v)}" for k, v in params.items() if v is not None
        )
        return (
            f"https://accounts.google.com/o/oauth2/v2/auth?{query}",
            state,
            code_verifier,
        )

    @staticmethod
    def authenticate(*, session: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by their email and password.

        Args:
            session (Session): The database session to use for querying.
            email (str): The email address of the user.
            password (str): The plain text password of the user.

        Returns:
            User | None: The authenticated user object
            if authentication is successful, otherwise None.
        """
        db_user = UserController.get_user_by_email(session=session, email=email)
        # Always run bcrypt regardless of whether the user exists so that response
        # time is constant and cannot be used to enumerate valid email addresses.
        hash_to_check = (
            db_user.hashed_password
            if db_user and db_user.hashed_password
            else _DUMMY_HASH
        )
        if not SecurityHelper.verify_password(password, hash_to_check):
            return None
        return db_user

    @staticmethod
    def get_tokens_expire() -> tuple[timedelta, timedelta]:
        """Get token expiration timedeltas for access and refresh tokens."""
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        return access_token_expires, refresh_token_expires

    @staticmethod
    def create_auth_tokens(user: User) -> tuple[str, str, str]:
        """
        Create authentication tokens for a user.

        Args:
            user (User): The user object for whom to create tokens.

        Returns:
            str: The JWT access token.
            str: The JWT refresh token.
            str: The JWT JTI key.
        """
        access_token_expires, refresh_token_expires = AuthController.get_tokens_expire()
        algo = settings.ACCESS_TOKEN_ALGORITHM
        access_signing_secret = _resolve_access_secret(algo)

        access_token, jti = SecurityHelper.create_access_token(
            data=TokenAccessData(
                sub=str(user.id),
                full_name=user.full_name,
                email=user.email,
                avatar=user.avatar,
                is_active=user.is_active,
                email_verified=user.email_verified,
                is_superuser=user.is_superuser,
                role=user.role,
            ),
            expires_delta=access_token_expires,
            secrets=access_signing_secret,
            issuer=settings.TOKEN_ISSUER or None,
            audience=settings.TOKEN_AUDIENCE or None,
            kid=_resolve_kid(algo),
        )
        refresh_token, _ = SecurityHelper.create_refresh_token(
            data=TokenMinimalData(
                sub=str(user.id),
                type="refresh",
            ),
            expires_delta=refresh_token_expires,
            secrets=TokenSecret(
                secret_key=settings.REFRESH_SECRET_KEY,
                algorithm=settings.REFRESH_TOKEN_ALGORITHM,
            ),
            jti=jti,
        )
        return access_token, refresh_token, jti

    @staticmethod
    def create_auth_session(
        *,
        session: Session,
        user: User,
        jti: str,
        refresh_token: str,
        external_token: Optional[ExternalTokensData] = None,
    ) -> ClientSession:
        """Add or update client session."""
        access_token_expires, refresh_token_expires = AuthController.get_tokens_expire()
        external_access, external_refresh, external_expires = None, None, None
        if external_token is not None:
            enc_key = settings.TOKENS_ENCRYPTION_KEY.get_secret_value()
            external_access = SecurityHelper.encrypt_token(
                external_token.access.get_secret_value(), enc_key
            )
            external_refresh = SecurityHelper.encrypt_token(
                external_token.refresh.get_secret_value(), enc_key
            )
            external_expires = datetime.now(timezone.utc) + timedelta(
                seconds=external_token.expires
            )
        session_data = ClientSessionCreate(
            jwt_jti=jti,
            refresh_token_hash=SecurityHelper.hash_token(refresh_token),
            jwt_expires_at=datetime.now(timezone.utc) + access_token_expires,
            refresh_expires_at=datetime.now(timezone.utc) + refresh_token_expires,
            external_access_token=external_access,
            external_refresh_token=external_refresh,
            external_token_expires_at=external_expires,
        )
        session_item = SessionController.create_client_session(
            session=session,
            current_user=user,
            session_data=session_data,
        )
        return session_item
