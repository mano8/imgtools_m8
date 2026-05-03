"""
Module for FastAPI authentication and dependency injection.

This module provides dependencies for obtaining a database session,
retrieving the current user from a JWT token, and ensuring the user has
active and superuser privileges.
"""
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from auth_sdk_m8.core.exceptions import InvalidToken
from redis import ConnectionPool, Redis

from auth_user_service.core.client import RedisSessionManager
from auth_user_service.core.config import settings
from auth_user_service.core.engine_sync import SessionDep
from auth_sdk_m8.core.security import ComSecurityHelper
from auth_sdk_m8.schemas.auth import TokenDecodeProps
from auth_sdk_m8.schemas.user import UserModel

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/login/access-token"
)
google_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/google-auth/oauth-callback/"
)
TokenDep = Annotated[str, Depends(reusable_oauth2)]
GoogleTokenDep = Annotated[str, Depends(google_oauth2)]

_redis_pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    username=settings.REDIS_USER,
    password=settings.REDIS_PASSWORD.get_secret_value() or None,
    decode_responses=True,
)

def get_current_user(
    token: TokenDep
) -> UserModel:
    """
    Retrieve the current user from the JWT token.

    Parameters:
        session:
            A database session dependency.
        token:
            The JWT token extracted from request headers.

    Returns:
        UserModel:
            The current authenticated user.

    Raises:
        HTTPException:
            If the JWT token is invalid, or the user is not found, or the
            user is inactive.
    """
    token_data = None
    try:
        payload = ComSecurityHelper.decode_access_token(
            token_data=TokenDecodeProps(
                access_token=token,
                secret_key=settings.ACCESS_SECRET_KEY,
                algorithm=settings.TOKEN_ALGORITHM
            )
        )
        is_session_revoked = RedisSessionManager(
            get_redis_client()).is_blacklisted(payload.jti)

        if is_session_revoked:
            raise InvalidTokenError("Session revoked")
        payload_dict = payload.model_dump(
            exclude={"exp", "jti", "type", "sub"}
        )
        payload_dict.update({"id": payload.sub})
        token_data = UserModel(**payload_dict)
    except (InvalidTokenError, InvalidToken, ValidationError) as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials.",
        ) from ex
    if token_data is None:  # pragma: no cover
        raise HTTPException(status_code=403, detail="Could not validate credentials.")
    if not token_data.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    return token_data


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


def get_current_active_superuser(
    current_user: CurrentUser
) -> UserModel:
    """
    Verify that the current user is an active superuser.

    Parameters:
        current_user:
            The currently authenticated user.

    Returns:
        UserModel:
            The current active superuser.

    Raises:
        HTTPException:
            If the current user does not have superuser privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


def get_templates():
    """
    Define Template directory
    """
    return Jinja2Templates(directory=settings.TEMPLATES_BASE_PATH)


def get_redis_client() -> Redis:
    """Get a Redis client from the shared connection pool."""
    return Redis(connection_pool=_redis_pool)


def verify_private_api_secret(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
) -> None:
    """Reject requests that do not carry the correct inter-service secret."""
    expected = settings.PRIVATE_API_SECRET.get_secret_value()
    if not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")
