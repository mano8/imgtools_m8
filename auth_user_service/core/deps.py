"""
FastAPI authentication dependencies.

Provides token validation, current-user extraction, Redis connectivity,
and role/privilege guards for auth_user_service routes.
"""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from redis import ConnectionPool, Redis

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.auth import TokenSecret
from auth_sdk_m8.schemas.user import UserModel
from auth_sdk_m8.security import TokenValidationConfig, TokenValidator

from auth_user_service.core.client import RedisSessionManager
from auth_user_service.core.config import settings
from auth_user_service.core.engine_sync import SessionDep  # noqa: F401 (re-exported)

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

# Module-level validator — created once at startup from validated settings.
_access_validator = TokenValidator(
    secrets=TokenSecret(
        secret_key=settings.ACCESS_SECRET_KEY,
        algorithm=settings.TOKEN_ALGORITHM,
    ),
    config=TokenValidationConfig(),
)


def get_redis_client() -> Redis:
    """Return a Redis client from the shared connection pool."""
    return Redis(connection_pool=_redis_pool)


RedisDep = Annotated[Redis, Depends(get_redis_client)]


def get_current_user(
    token: TokenDep,
    redis: RedisDep,
) -> UserModel:
    """Validate the access token and return the authenticated user.

    Args:
        token: JWT string extracted from the Authorization header.
        redis: Redis client (injected via Depends).

    Returns:
        Authenticated ``UserModel``.

    Raises:
        HTTPException 401: Token revoked.
        HTTPException 403: Token invalid, expired, or user inactive.
    """
    try:
        payload = _access_validator.validate_access_token(token)
    except InvalidToken as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials.",
        ) from ex

    if RedisSessionManager(redis).is_blacklisted(payload.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked",
        )

    if not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    payload_dict = payload.model_dump(exclude={"exp", "jti", "type", "sub"})
    payload_dict["id"] = payload.sub
    return UserModel(**payload_dict)


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> UserModel:
    """Verify that the current user holds superuser privileges.

    Raises:
        HTTPException 403: Insufficient privileges.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


def get_templates() -> Jinja2Templates:
    """Return the Jinja2 template engine bound to the configured directory."""
    return Jinja2Templates(directory=settings.TEMPLATES_BASE_PATH)


def verify_private_api_secret(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
) -> None:
    """Reject requests that do not carry the correct inter-service secret."""
    expected = settings.PRIVATE_API_SECRET.get_secret_value()
    if not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
