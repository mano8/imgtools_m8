"""
Authentication Views (Login, Logout, Refresh)

Handles email/password login and refresh-token rotation, issuing internal JWTs,
persisting session metadata, and managing token revocation via Redis.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.models.shared import Token
from auth_sdk_m8.schemas.auth import TokenSecret
from auth_sdk_m8.schemas.base import ResponseMessage

from auth_user_service.core.client import LoginRateLimiter, RedisRefreshStore
from auth_user_service.core.config import settings
from auth_user_service.core.deps import (
    CurrentUser,
    RedisDep,
    SessionDep,
    TokenDep,
    _access_validator,
)
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import UserPublic
from auth_user_service.services.auth import AuthController
from auth_user_service.services.client_sessions import SessionController
from auth_user_service.services.users import UserController

logger = logging.getLogger(__name__)

router = APIRouter(tags=["login"], prefix="/login")

_SECURE_COOKIE = settings.ENVIRONMENT != "local"
_REFRESH_TTL_SECONDS = settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60

_REFRESH_SECRETS = TokenSecret(
    secret_key=settings.REFRESH_SECRET_KEY,
    algorithm=settings.REFRESH_TOKEN_ALGORITHM,
)


@router.post("/access-token", response_model=Token)
def login_access_token(
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Authenticate via email/password and issue JWT tokens."""
    email = form_data.username

    if redis is not None:
        rate_limiter = LoginRateLimiter(redis)
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

    if redis is not None:
        LoginRateLimiter(redis).reset(email)

    access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)

    if settings.TOKEN_MODE != "stateless":
        AuthController.create_auth_session(
            session=session,
            user=user,
            jti=jti,
            refresh_token=refresh_token,
        )
        # Register the refresh JTI in the allowlist so rotation can validate it.
        if redis is not None:
            RedisRefreshStore(redis).register(jti, _REFRESH_TTL_SECONDS)

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
    redis: RedisDep,
    refresh_token: str = Depends(SecurityHelper.get_refresh_token_from_cookie),
) -> Token:
    """Refresh access token using a valid refresh token.

    The old JTI is atomically swapped for the new one (rotation).
    Presenting an already-consumed JTI is treated as a reuse attack and
    immediately rejected — the allowlist entry will be absent.
    """
    try:
        user_id, old_jti = SecurityHelper.decode_refresh_token(
            refresh_token,
            secrets=_REFRESH_SECRETS,
            return_jti=True,
        )
    except InvalidToken as err:
        raise HTTPException(status_code=401, detail=str(err)) from err

    # Allowlist check: stateful/hybrid modes require the JTI to be registered.
    if settings.TOKEN_MODE != "stateless" and redis is not None:
        if not RedisRefreshStore(redis).is_valid(old_jti):
            response.delete_cookie(key="refresh_token")
            raise HTTPException(status_code=401, detail="Token revoked or reused")

    user = UserController.get_user(session=session, user_id=user_id)
    if user is None or user.is_active is not True:
        raise HTTPException(status_code=401, detail="Invalid user or inactive user")

    access_token, new_refresh_token, new_jti = AuthController.create_auth_tokens(user=user)

    if settings.TOKEN_MODE != "stateless":
        AuthController.create_auth_session(
            session=session,
            user=user,
            jti=new_jti,
            refresh_token=new_refresh_token,
        )
        # Atomically swap old JTI for new one — any reuse of old_jti is now detectable.
        if redis is not None:
            RedisRefreshStore(redis).rotate(old_jti, new_jti, _REFRESH_TTL_SECONDS)

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
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
    redis: RedisDep,
    refresh_token: str = Depends(SecurityHelper.get_refresh_token_from_cookie),
) -> ResponseMessage:
    """Revoke both tokens and clear the refresh-token cookie."""
    # Revoke refresh token from the allowlist.
    if redis is not None and settings.TOKEN_MODE != "stateless":
        try:
            _, refresh_jti = SecurityHelper.decode_refresh_token(
                refresh_token,
                secrets=_REFRESH_SECRETS,
                return_jti=True,
            )
            RedisRefreshStore(redis).revoke(refresh_jti)
        except Exception:
            logger.warning("Could not revoke refresh JTI on logout.")

    # Blacklist the access token JTI so it cannot be used until natural expiry.
    if settings.TOKEN_MODE == "stateful":
        try:
            payload = _access_validator.validate_access_token(token)
            if payload.exp is not None:
                expires_at = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
            else:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            SessionController.revoke_session_jti(payload.jti, expires_at)
        except Exception:
            logger.warning("Could not blacklist access token JTI on logout.")

    response.delete_cookie(key="refresh_token")
    return ResponseMessage(success=True, msg="Logged out successfully")


@router.post("/test-token/", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """Return the current user — use to verify a valid access token."""
    return current_user
