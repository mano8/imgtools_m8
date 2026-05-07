"""
AuthController.py
===================
"""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional, Union
from urllib.parse import quote_plus

from sqlmodel import Session

from auth_user_service.services.client_sessions import SessionController
from auth_user_service.services.users import UserController
from auth_user_service.db_models.users import User
from auth_user_service.db_models.sessions import (
    ClientSessionCreate,
    ClientSession
)
from auth_user_service.core.client import PKCEStore
from auth_user_service.core.config import settings
from auth_user_service.core.deps import get_redis_client
from auth_user_service.core.security import SecurityHelper

from auth_sdk_m8.schemas.auth import ExternalTokensData, TokenAccessData, TokenMinimalData, TokenSecret


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
    def get_google_login_url(cls, redirect_uri: Optional[str] = None) -> str:
        """
        Generates the Google OAuth2 login URL with PKCE parameters.

        Args:
            redirect_uri: The OAuth2 callback URI registered in Google API Console.

        Returns:
            A redirect URL string for initiating Google OAuth2 with PKCE.
        """
        state = cls.create_state()
        code_verifier = cls.generate_code_verifier()
        code_challenge = cls.generate_code_challenge(code_verifier)
        pkce_store = PKCEStore(get_redis_client())
        pkce_store.store(state, code_verifier)

        params = {
            "response_type": "code",
            "client_id": settings.GOOGLE_CLIENT_ID.get_secret_value(),
            "redirect_uri": redirect_uri,
            "scope": "openid email profile https://www.googleapis.com/auth/forms.body.readonly",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        query = "&".join(
            f"{k}={quote_plus(v)}"
            for k, v in params.items()
            if v is not None
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    @staticmethod
    def authenticate(
        *,
        session: Session,
        email: str,
        password: str
    ) -> Optional[User]:
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
        db_user = UserController.get_user_by_email(
            session=session, email=email)
        if not db_user:
            return None
        if not SecurityHelper.verify_password(password, db_user.hashed_password):
            return None
        return db_user

    @staticmethod
    def get_tokens_expire() -> Union[timedelta, timedelta]:
        """
        Get tokens expiarition timedelta.
        """
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        refresh_token_expires = timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
        return access_token_expires, refresh_token_expires

    @staticmethod
    def create_auth_tokens(
        user: User
    ) -> Union[str, str, str]:
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
        access_token, jti = SecurityHelper.create_access_token(
            data=TokenAccessData(
                sub=user.id,
                full_name=user.full_name,
                email=user.email,
                avatar=user.avatar,
                is_active=user.is_active,
                email_verified=user.email_verified,
                is_superuser=user.is_superuser,
                role=user.role,
            ),
            expires_delta=access_token_expires,
            secrets=TokenSecret(
                secret_key=settings.ACCESS_SECRET_KEY,
                algorithm=settings.ACCESS_TOKEN_ALGORITHM,
            ),
        )
        refresh_token, _ = SecurityHelper.create_refresh_token(
            data=TokenMinimalData(
                sub=user.id,
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
        external_token: Optional[ExternalTokensData] = None
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
