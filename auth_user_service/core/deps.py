"""
FastAPI authentication dependencies.

Provides token validation, current-user extraction, Redis connectivity,
and role/privilege guards for auth_user_service routes.
"""

import logging
import secrets
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from redis import ConnectionPool, Redis

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.user import UserModel
from auth_sdk_m8.security import (
    ValidationHooks,
    build_access_validator,
)

from auth_user_service.core.client import RedisSessionManager
from auth_user_service.core.config import settings
from auth_sdk_m8.observability.metrics import get as _get_metrics
from auth_user_service.core.engine_sync import SessionDep  # noqa: F401 (re-exported)

_logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/login/access-token"
)
google_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/google-auth/oauth-callback/"
)
TokenDep = Annotated[str, Depends(reusable_oauth2)]
GoogleTokenDep = Annotated[str, Depends(google_oauth2)]


class _LoggingHooks:
    """Emit structured log lines for every token validation outcome."""

    def on_success(self, *, jti: str, sub: str, token_type: str) -> None:
        _logger.debug("token.valid type=%s sub=%s jti=%s", token_type, sub, jti)

    def on_failure(self, *, reason: str, token_type: str) -> None:
        _logger.warning("token.invalid type=%s reason=%s", token_type, reason)


_hooks: ValidationHooks = _LoggingHooks()

# Redis pool is skipped entirely in stateless mode.
_redis_pool: Optional[ConnectionPool] = (
    ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USER,
        password=settings.REDIS_PASSWORD.get_secret_value() or None,
        decode_responses=True,
    )
    if settings.TOKEN_MODE != "stateless"
    else None
)


# Module-level validator — created once at startup from validated settings.
# iss/aud enforcement is opt-in: set TOKEN_ISSUER / TOKEN_AUDIENCE in env to
# enable.  When unset, validation is permissive for backward compatibility.
_access_validator = build_access_validator(settings, _hooks)


def get_redis_client() -> Optional[Redis]:
    """Return a Redis client from the shared pool, or None when unavailable.

    A ping is issued on every call so that ``if redis is not None:`` guards in
    routes correctly reflect the actual connection state rather than always
    passing because the pool object exists.
    """
    if _redis_pool is None:
        return None
    try:
        client = Redis(connection_pool=_redis_pool)
        client.ping()
        return client
    except Exception:
        _logger.warning("redis.unavailable degraded_mode=true")
        return None


RedisDep = Annotated[Optional[Redis], Depends(get_redis_client)]


def get_current_user(token: TokenDep) -> UserModel:
    """Validate the access token and return the authenticated user.

    Args:
        token: JWT string extracted from the Authorization header.

    Returns:
        Authenticated ``UserModel``.

    Raises:
        HTTPException 401: Token revoked (stateful mode only).
        HTTPException 403: Token invalid, expired, or user inactive.
    """
    try:
        payload = _access_validator.validate_access_token(token)
    except InvalidToken as ex:
        _m = _get_metrics()
        if _m and _m.token_validation_failures_total:
            _m.token_validation_failures_total.labels(reason="invalid").inc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials.",
        ) from ex

    # JTI blacklist check only applies in stateful mode.
    # In hybrid mode, access tokens are stateless; only refresh JTIs are tracked.
    if settings.TOKEN_MODE == "stateful":
        redis = get_redis_client()
        if redis is not None and RedisSessionManager(redis).is_blacklisted(payload.jti):
            _m = _get_metrics()
            if _m and _m.token_validation_failures_total:
                _m.token_validation_failures_total.labels(reason="revoked").inc()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session revoked",
            )

    if not payload.is_active:
        _m = _get_metrics()
        if _m and _m.token_validation_failures_total:
            _m.token_validation_failures_total.labels(reason="inactive").inc()
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
