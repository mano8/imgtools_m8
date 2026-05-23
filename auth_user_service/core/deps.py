"""
FastAPI authentication dependencies.

Provides token validation, current-user extraction, Redis connectivity,
and role/privilege guards for auth_user_service routes.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, Response, status
from fastapi.security import OAuth2PasswordBearer
from redis import ConnectionPool, Redis
from sqlmodel import Session

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
from auth_user_service.db_models.api_keys import ApiKey
from auth_user_service.services.api_keys import ApiKeyService, RateLimitEnforcer

# Redis hash key for write-behind last_used_at updates: field=key_id, value=ISO timestamp
LAST_USED_AT_HASH = "api_key:luat"

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
        _logger.info(
            "event=token.valid type=%s sub=%s jti=%s ts=%s",
            token_type,
            sub,
            jti,
            datetime.now(timezone.utc).isoformat(),
        )

    def on_failure(self, *, reason: str, token_type: str) -> None:
        _logger.warning(
            "event=token.invalid type=%s reason=%s ts=%s",
            token_type,
            reason,
            datetime.now(timezone.utc).isoformat(),
        )


_hooks: ValidationHooks = _LoggingHooks()

_redis_degraded_since: Optional[datetime] = None
_REDIS_CIRCUIT_BREAKER_SECS = 30
_REDIS_CONNECT_TIMEOUT_SECS = 2

_ssl_kwargs: dict[str, object] = (
    {
        "ssl": True,
        **({"ssl_ca_certs": settings.REDIS_SSL_CA} if settings.REDIS_SSL_CA else {}),
        **(
            {"ssl_certfile": settings.REDIS_SSL_CERT} if settings.REDIS_SSL_CERT else {}
        ),
        **({"ssl_keyfile": settings.REDIS_SSL_KEY} if settings.REDIS_SSL_KEY else {}),
    }
    if settings.REDIS_SSL
    else {}
)
_redis_pool: Optional[ConnectionPool] = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    username=settings.REDIS_USER,
    password=settings.REDIS_PASSWORD.get_secret_value() or None,
    decode_responses=True,
    socket_connect_timeout=_REDIS_CONNECT_TIMEOUT_SECS,
    socket_timeout=_REDIS_CONNECT_TIMEOUT_SECS,
    **_ssl_kwargs,
)


# Module-level validator — created once at startup from validated settings.
# iss/aud enforcement is opt-in: set TOKEN_ISSUER / TOKEN_AUDIENCE in env to
# enable.  When unset, validation is permissive for backward compatibility.
_access_validator = build_access_validator(settings, _hooks)


def get_redis_client() -> Optional[Redis]:
    """Return a Redis client from the shared pool, or None when unavailable.

    Circuit breaker: after the first failure, skips the ping for
    ``_REDIS_CIRCUIT_BREAKER_SECS`` seconds so that an unreachable Redis
    server does not add per-request latency. Resets on first successful ping.
    """
    global _redis_degraded_since
    if _redis_pool is None:
        return None
    if _redis_degraded_since is not None:
        elapsed = (datetime.now(timezone.utc) - _redis_degraded_since).total_seconds()
        if elapsed < _REDIS_CIRCUIT_BREAKER_SECS:
            return None
    try:
        client = Redis(connection_pool=_redis_pool)
        client.ping()
        _redis_degraded_since = None
        _m = _get_metrics()
        if _m and _m.redis_circuit_breaker_open:
            _m.redis_circuit_breaker_open.set(0)
        return client
    except Exception as exc:
        if _redis_degraded_since is None:
            _redis_degraded_since = datetime.now(timezone.utc)
        _logger.warning("redis.unavailable degraded_mode=true error=%s", exc)
        _m = _get_metrics()
        if _m and _m.redis_circuit_breaker_open:
            _m.redis_circuit_breaker_open.set(1)
        return None


def get_redis_degraded_since() -> Optional[datetime]:
    """Return the UTC timestamp when Redis first became unreachable, or None."""
    return _redis_degraded_since


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
    if settings.is_stateful:
        redis = get_redis_client()
        if redis is None:
            _mode = settings.effective_failure_mode("access_revocation")
            _m = _get_metrics()
            if _m and _m.degraded_decision_total:
                _m.degraded_decision_total.labels(
                    control="access_revocation", mode=_mode, reason="redis_unavailable"
                ).inc()
            if _mode == "fail_closed":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable",
                )
        elif RedisSessionManager(redis).is_blacklisted(payload.jti):
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


def verify_private_api_secret(
    x_internal_token: str = Header(..., alias="X-Internal-Token"),
) -> None:
    """Reject requests that do not carry the correct inter-service secret."""
    expected = settings.PRIVATE_API_SECRET.get_secret_value()
    if not secrets.compare_digest(x_internal_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )


def _apply_rate_limit(
    redis: Redis,
    session: Session,
    api_key: ApiKey,
    response: Response,
) -> None:
    """Enforce rate limits and write X-RateLimit-* headers. Raises 429 if exceeded."""
    limits = ApiKeyService.get_limits(session, api_key.id, api_key.user_id)
    result = RateLimitEnforcer(redis, settings).enforce(api_key, limits)

    if not result.allowed:
        retry_after = 60
        if result.reset_at is not None:
            retry_after = max(
                1,
                int((result.reset_at - datetime.now(timezone.utc)).total_seconds()) + 1,
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for period: {result.exceeded_period}",
            headers={"Retry-After": str(retry_after)},
        )

    if result.limit is not None:
        response.headers["X-RateLimit-Limit"] = str(result.limit)
    if result.remaining is not None:
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    if result.reset_at is not None:
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_at.timestamp()))

    try:
        redis.hset(
            LAST_USED_AT_HASH,
            str(api_key.id),
            datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        ref = str(api_key.id)
        _logger.warning("luat.write_failed ref=%s", ref)


def get_current_api_key(
    session: SessionDep,
    redis: RedisDep,
    response: Response,
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
) -> ApiKey:
    """Validate an API key and enforce rate limits.

    Reads the ``X-API-Key`` header, validates the key, runs rate limit checks
    when Redis is available, and queues a write-behind ``last_used_at`` update.
    Sets ``X-RateLimit-*`` response headers when limits are enforced.

    Raises:
        HTTPException 401: Key missing, invalid, expired, or revoked.
        HTTPException 429: Rate limit exceeded (includes ``Retry-After`` header).
        HTTPException 503: Strict mode and Redis unavailable.
    """
    api_key = ApiKeyService.get_active_key(session, x_api_key)
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    if redis is not None:
        _apply_rate_limit(redis, session, api_key, response)
    elif settings.API_KEY_STRICT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service unavailable",
        )

    return api_key


CurrentApiKey = Annotated[ApiKey, Depends(get_current_api_key)]
