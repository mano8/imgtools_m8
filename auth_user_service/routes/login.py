"""
Authentication Views (Login, Logout, Refresh)

This module handles both Google OAuth2 login and traditional
email/password login, issuing internal JWTs, persisting
session metadata (including external Google tokens), and
managing refresh token revocation via Redis.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm

from auth_user_service.core.deps import CurrentUser, SessionDep
from auth_user_service.services.auth import AuthController
from auth_user_service.services.client_sessions import SessionController
from auth_user_service.services.users import UserController
from auth_user_service.core.client import LoginRateLimiter
from auth_user_service.core.config import settings
from auth_user_service.core.deps import TokenDep, get_redis_client
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import UserPublic
from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.core.security import ComSecurityHelper
from auth_sdk_m8.models.shared import Token
from auth_sdk_m8.schemas.auth import TokenDecodeProps, TokenSecret
from auth_sdk_m8.schemas.base import ResponseMessage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["login"], prefix="/login")

_SECURE_COOKIE = settings.ENVIRONMENT != "local"


@router.post("/access-token", response_model=Token)
def login_access_token(
    response: Response,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    Authenticate via email/password and issue JWT tokens.
    """
    email = form_data.username
    rate_limiter = LoginRateLimiter(get_redis_client())

    if not rate_limiter.is_allowed(email):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in 15 minutes.",
        )

    user = AuthController.authenticate(
        session=session,
        email=email,
        password=form_data.password,
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Invalid credentials or inactive user",
        )

    rate_limiter.reset(email)

    access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)
    AuthController.create_auth_session(
        session=session,
        user=user,
        jti=jti,
        refresh_token=refresh_token,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS,
    )
    return Token(access_token=access_token)


@router.post("/refresh-token/", response_model=Token)
def login_refresh_token(
    response: Response,
    session: SessionDep,
    refresh_token: str = Depends(SecurityHelper.get_refresh_token_from_cookie),
) -> Token:
    """
    Refresh internal access token using a valid refresh token.
    """
    try:
        user_id, jti = SecurityHelper.decode_refresh_token(
            refresh_token,
            secrets=TokenSecret(
                secret_key=settings.REFRESH_SECRET_KEY,
                algorithm=settings.TOKEN_ALGORITHM,
            ),
            return_jti=True,
        )
    except InvalidToken as err:
        raise HTTPException(status_code=401, detail=str(err)) from err

    if SessionController.is_session_revoked(jti):
        response.delete_cookie(key="refresh_token")
        raise HTTPException(status_code=401, detail="Token revoked")

    user = UserController.get_user(session=session, user_id=user_id)
    if user is None or user.is_active is not True:
        raise HTTPException(
            status_code=401,
            detail="Invalid user or inactive user",
        )

    access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)
    AuthController.create_auth_session(
        session=session,
        user=user,
        jti=jti,
        refresh_token=refresh_token,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS,
    )
    return Token(access_token=access_token)


@router.post("/logout/", response_model=ResponseMessage)
def logout(
    response: Response,
    token: TokenDep,
    refresh_token: str = Depends(SecurityHelper.get_refresh_token_from_cookie),
) -> ResponseMessage:
    """
    Logout by blacklisting the shared JTI (invalidates both tokens) and
    clearing the refresh-token cookie.
    """
    try:
        _, jti = SecurityHelper.decode_refresh_token(
            refresh_token,
            secrets=TokenSecret(
                secret_key=settings.REFRESH_SECRET_KEY,
                algorithm=settings.TOKEN_ALGORITHM,
            ),
            return_jti=True,
        )
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
        )
        SessionController.revoke_session_jti(jti, expires_at)
    except Exception:
        logger.warning("Could not revoke via refresh token; trying access token.")
        try:
            payload = ComSecurityHelper.decode_access_token(
                token_data=TokenDecodeProps(
                    access_token=token,
                    secret_key=settings.ACCESS_SECRET_KEY,
                    algorithm=settings.TOKEN_ALGORITHM,
                )
            )
            expires_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            SessionController.revoke_session_jti(payload.jti, expires_at)
        except Exception:
            logger.warning("Could not revoke access token JTI on logout.")

    response.delete_cookie(key="refresh_token")
    return ResponseMessage(success=True, msg="Logged out successfully")


@router.post("/login/test-token/", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user
