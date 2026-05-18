"""
Authentication Views (Login, Logout, Refresh)

Handles email/password login and refresh-token rotation, issuing internal JWTs,
persisting session metadata, and managing token revocation via Redis.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.models.shared import Token
from auth_sdk_m8.schemas.auth import TokenSecret
from auth_sdk_m8.schemas.base import ResponseMessage

from auth_user_service.core.client import LoginRateLimiter, RedisRefreshStore, RefreshRateLimiter
from auth_user_service.core.config import settings
from auth_sdk_m8.observability.metrics import get as _get_metrics
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


def _get_refresh_cookie(
    t: str = Cookie(None, alias="refresh_token"),
) -> str:
    """Extract refresh token from HttpOnly cookie for FastAPI dependency injection."""
    return SecurityHelper.get_refresh_token_from_cookie(t)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Request) -> str:
    # Correctness relies on Traefik stripping client-supplied X-Forwarded-For
    # at the entrypoint boundary (forwardedHeaders.trustedIPs in traefik.yml).
    # The leftmost IP is the real client only because the proxy chain is trusted.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/access-token", response_model=Token)
def login_access_token(
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Authenticate via email/password and issue JWT tokens."""
    email = form_data.username
    ip = _client_ip(request)

    if "\x00" in email or "\x00" in form_data.password:
        raise HTTPException(status_code=422, detail="Invalid characters in credentials")

    _m = _get_metrics()

    if redis is not None:
        rate_limiter = LoginRateLimiter(redis)
        if not rate_limiter.is_allowed(email):
            if _m and _m.login_attempts_total:
                _m.login_attempts_total.labels(result="rate_limited").inc()
            logger.warning("event=login.rate_limited ip=%s ts=%s", ip, _now_iso())
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Try again in 15 minutes.",
            )
    elif settings.effective_failure_mode("rate_limit") == "fail_closed":
        raise HTTPException(
            status_code=503,
            detail="Rate limiting service temporarily unavailable",
        )

    user = AuthController.authenticate(
        session=session,
        email=email,
        password=form_data.password,
    )

    if not user or not user.is_active:
        reason = "inactive_user" if user else "wrong_credentials"
        if _m and _m.login_attempts_total:
            _m.login_attempts_total.labels(result=reason).inc()
        logger.warning(
            "event=login.failure reason=%s ip=%s ts=%s", reason, ip, _now_iso()
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid credentials or inactive user",
        )

    if redis is not None:
        LoginRateLimiter(redis).reset(email)

    if _m and _m.login_attempts_total:
        _m.login_attempts_total.labels(result="success").inc()

    logger.info(
        "event=login.success user_id=%s ip=%s ts=%s", str(user.id), ip, _now_iso()
    )

    access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)

    if not settings.is_stateless:
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
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS,
    )
    return Token(access_token=access_token)


@router.post("/refresh-token/", response_model=Token)
def login_refresh_token(
    request: Request,
    response: Response,
    session: SessionDep,
    redis: RedisDep,
    refresh_token: str = Depends(_get_refresh_cookie),
) -> Token:
    """Refresh access token using a valid refresh token.

    The old JTI is atomically swapped for the new one (rotation).
    Presenting an already-consumed JTI is treated as a reuse attack and
    immediately rejected — the allowlist entry will be absent.
    """
    ip = _client_ip(request)
    _m = _get_metrics()

    try:
        user_id, old_jti = SecurityHelper.decode_refresh_token(
            refresh_token,
            secrets=_REFRESH_SECRETS,
            return_jti=True,
        )
    except InvalidToken as err:
        if _m and _m.token_refresh_total:
            _m.token_refresh_total.labels(result="invalid").inc()
        raise HTTPException(status_code=401, detail=str(err)) from err

    if redis is not None:
        if not RefreshRateLimiter(redis).is_allowed(str(user_id)):
            if _m and _m.token_refresh_total:
                _m.token_refresh_total.labels(result="rate_limited").inc()
            logger.warning(
                "event=refresh.rate_limited user_id=%s ip=%s ts=%s",
                str(user_id),
                ip,
                _now_iso(),
            )
            raise HTTPException(
                status_code=429,
                detail="Too many refresh attempts. Try again later.",
            )
    elif settings.effective_failure_mode("rate_limit") == "fail_closed":
        raise HTTPException(
            status_code=503,
            detail="Rate limiting service temporarily unavailable",
        )

    # Allowlist check: stateful/hybrid modes require the JTI to be registered.
    if not settings.is_stateless:
        if redis is None:
            if settings.effective_failure_mode("refresh_validation") == "fail_closed":
                raise HTTPException(
                    status_code=503,
                    detail="Authentication service temporarily unavailable",
                )
        elif not RedisRefreshStore(redis).is_valid(old_jti):
            if _m and _m.token_refresh_total:
                _m.token_refresh_total.labels(result="revoked").inc()
            response.delete_cookie(key="refresh_token")
            raise HTTPException(status_code=401, detail="Token revoked or reused")

    user = UserController.get_user(session=session, user_id=user_id)
    if user is None or user.is_active is not True:
        raise HTTPException(status_code=401, detail="Invalid user or inactive user")

    access_token, new_refresh_token, new_jti = AuthController.create_auth_tokens(
        user=user
    )

    if not settings.is_stateless:
        # Rotate first: if the Lua script finds old_jti already gone, a concurrent
        # request won the race or this is a reuse attack — reject before any DB write.
        if redis is not None:
            rotated = RedisRefreshStore(redis).rotate(
                old_jti, new_jti, _REFRESH_TTL_SECONDS
            )
            if not rotated:
                if _m and _m.token_refresh_total:
                    _m.token_refresh_total.labels(result="revoked").inc()
                logger.warning(
                    "event=token.reuse user_id=%s old_jti=%s ip=%s ts=%s",
                    str(user_id),
                    old_jti,
                    ip,
                    _now_iso(),
                )
                # Reuse confirmed — invalidate every session for this user so the
                # attacker's already-rotated tokens also stop working.
                SessionController.revoke_all_user_sessions(session, str(user_id), redis)
                response.delete_cookie(key="refresh_token")
                raise HTTPException(
                    status_code=401,
                    detail="Token reuse detected. All sessions revoked. Please log in again.",
                )
        AuthController.create_auth_session(
            session=session,
            user=user,
            jti=new_jti,
            refresh_token=new_refresh_token,
        )

    if _m and _m.token_refresh_total:
        _m.token_refresh_total.labels(result="success").inc()

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS,
    )
    return Token(access_token=access_token)


@router.post("/logout/", response_model=ResponseMessage)
def logout(
    response: Response,
    session: SessionDep,
    token: TokenDep,
    redis: RedisDep,
    refresh_token: str = Depends(_get_refresh_cookie),
) -> ResponseMessage:
    """Revoke both tokens, delete the DB session, and clear the cookie."""
    jti: str | None = None
    _revocation_failed = False
    _m = _get_metrics()

    # Blacklist the access token JTI so it cannot be reused until natural expiry.
    if settings.is_stateful:
        try:
            payload = _access_validator.validate_access_token(token)
            jti = payload.jti
            if payload.exp is not None:
                expires_at = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
            else:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
                )
            SessionController.revoke_session_jti(payload.jti, expires_at, redis)
        except Exception:  # noqa: BLE001
            logger.error("Could not blacklist access token JTI on logout.")
            if _m and _m.revocation_failure_total:
                _m.revocation_failure_total.labels(operation="access_blacklist").inc()
            _revocation_failed = True

    # Revoke the refresh JTI from the Redis allowlist.
    if not settings.is_stateless:
        if redis is not None:
            try:
                _, refresh_jti = SecurityHelper.decode_refresh_token(
                    refresh_token,
                    secrets=_REFRESH_SECRETS,
                    return_jti=True,
                )
                RedisRefreshStore(redis).revoke(refresh_jti)
                if jti is None:
                    jti = refresh_jti
            except Exception:  # noqa: BLE001
                logger.error("Could not revoke refresh JTI on logout.")
                if _m and _m.revocation_failure_total:
                    _m.revocation_failure_total.labels(operation="refresh_allowlist").inc()
                _revocation_failed = True
        elif settings.effective_failure_mode("session_write") == "fail_closed":
            logger.error("Could not revoke refresh JTI on logout: Redis unavailable.")
            if _m and _m.revocation_failure_total:
                _m.revocation_failure_total.labels(operation="refresh_allowlist").inc()
            _revocation_failed = True

    # Remove the DB session record.
    if not settings.is_stateless and jti is not None:
        try:
            SessionController.delete_session_by_jti(session=session, jti=jti)
        except Exception:  # noqa: BLE001
            logger.error("Could not delete DB session on logout.")
            if _m and _m.revocation_failure_total:
                _m.revocation_failure_total.labels(operation="db_session").inc()
            _revocation_failed = True

    if _revocation_failed and settings.effective_failure_mode("session_write") == "fail_closed":
        raise HTTPException(
            status_code=503,
            detail="Logout failed: session could not be fully revoked. Please try again.",
        )

    if _m and _m.logout_total:
        _m.logout_total.inc()

    response.delete_cookie(key="refresh_token")
    return ResponseMessage(success=True, msg="Logged out successfully")


@router.post("/test-token/", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """Return the current user — use to verify a valid access token."""
    return current_user
