"""FastAPI authentication dependencies.

Provides token validation, current-user extraction, and role-based access
helpers for service routes.
"""

import logging
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from redis import ConnectionPool, Redis

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.base import RoleType
from auth_sdk_m8.schemas.user import UserModel
from auth_sdk_m8.security import (
    AccessTokenBlacklist,
    ValidationHooks,
    build_access_validator,
)

from fastapi_service.core.config import settings

_logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.AUTH_PREFIX}/login/access-token"
)
TokenDep = Annotated[str, Depends(reusable_oauth2)]


class _LoggingHooks:
    """Emit structured log lines for every token validation outcome."""

    def on_success(self, *, jti: str, sub: str, token_type: str) -> None:
        _logger.debug("token.valid type=%s sub=%s jti=%s", token_type, sub, jti)

    def on_failure(self, *, reason: str, token_type: str) -> None:
        _logger.warning("token.invalid type=%s reason=%s", token_type, reason)


_hooks: ValidationHooks = _LoggingHooks()

# Module-level validator — created once at startup, not per-request.
# iss/aud enforcement is opt-in via TOKEN_ISSUER / TOKEN_AUDIENCE settings.
_validator = build_access_validator(settings, _hooks)

# Shared connection pool — avoids creating a new TCP connection on every
# request.  Skipped entirely in stateless mode (no Redis needed).
_redis_pool: Optional[ConnectionPool] = (
    ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USER,
        password=settings.REDIS_PASSWORD.get_secret_value() or None,
        decode_responses=True,
    )
    if settings.requires_redis
    else None
)


def get_redis_client() -> Optional[Redis]:
    """Return a Redis client from the shared pool, or None when unavailable.

    A ping is issued on every call so that ``if redis is not None:`` guards
    correctly reflect the actual connection state.
    """
    if _redis_pool is None:
        return None
    try:
        client = Redis(connection_pool=_redis_pool)
        client.ping()
        return client
    except Exception:
        _logger.warning("redis.unavailable blacklist_check=skipped")
        return None


RedisDep = Annotated[Optional[Redis], Depends(get_redis_client)]


def get_current_user(token: TokenDep, redis: RedisDep) -> UserModel:
    """Retrieve the current user from the JWT access token.

    Args:
        token: JWT string extracted from the Authorization header.
        redis: Optional Redis client; None when Redis is unavailable.

    Returns:
        Authenticated ``UserModel``.

    Raises:
        HTTPException 403: Token invalid, expired, revoked, or user inactive.
    """
    try:
        payload = _validator.validate_access_token(token)
    except InvalidToken as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials.",
        ) from ex

    # In stateful mode, verify the JTI has not been blacklisted by auth service.
    if settings.is_stateful and redis is not None:
        if AccessTokenBlacklist(redis).is_revoked(payload.jti):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token has been revoked.",
            )

    payload_dict = payload.model_dump(exclude={"exp", "jti", "type", "sub"})
    payload_dict["id"] = payload.sub
    user = UserModel(**payload_dict)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


class UserRoleHelper:
    """Role-based access guard helpers."""

    @staticmethod
    def get_current_active_superuser(current_user: CurrentUser) -> UserModel:
        """Verify the current user holds SUPERADMIN role.

        Raises:
            HTTPException 403: Insufficient privileges.
        """
        if not current_user.is_superuser or not RoleType.is_valid_role_auth(
            current_role=current_user.role,
            role_limit=RoleType.SUPERADMIN,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )
        return current_user

    @staticmethod
    def get_current_active_admin(current_user: CurrentUser) -> UserModel:
        """Verify the current user holds at least ADMIN role.

        Raises:
            HTTPException 403: Insufficient privileges.
        """
        if not RoleType.is_valid_role_auth(
            current_role=current_user.role,
            role_limit=RoleType.ADMIN,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )
        return current_user
