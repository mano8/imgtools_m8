"""Google OAuth2 callback — native-app auth code bridge."""

import json
import logging
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from httpx import HTTPError as HTTPXError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import SecretStr

from auth_user_service.services.auth import AuthController
from auth_user_service.db_models.users import User, UserCreate
from auth_user_service.core.deps import SessionDep
from auth_user_service.services.client_sessions import SessionController
from auth_user_service.services.users import UserController
from auth_user_service.services.oauth import OAuthController
from auth_user_service.core.client import (
    AuthCodeStore,
    OAuthSessionStore,
    RedisRefreshStore,
)
from auth_user_service.core.deps import get_redis_client
from auth_user_service.core.config import settings
from auth_sdk_m8.observability.metrics import get as _get_metrics

from auth_sdk_m8.schemas.auth import ExternalTokensData
from auth_sdk_m8.schemas.base import AuthProviderType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-auth", tags=["google-auth"])

_SECURE_COOKIE = settings.ENVIRONMENT != "local"
_REFRESH_TTL_SECONDS = settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60


def _get_oauth_session(redis: object, state: str) -> dict:
    """Retrieve and parse the OAuth session; raises 400 if missing/expired."""
    raw_session = OAuthSessionStore(redis).get(state)  # type: ignore[arg-type]
    if not raw_session:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter",
        )
    return json.loads(raw_session)


def _get_or_create_user(session: SessionDep, oauth_token: object) -> User:
    """Return the existing user or create one from the OAuth token data."""
    user = UserController.get_user_by_email(
        session=session,
        email=oauth_token.email,  # type: ignore[attr-defined]
    )
    if user is None:
        user_in = UserCreate(
            provider=AuthProviderType.GOOGLE,
            oauth_user_id=oauth_token.user_id,  # type: ignore[attr-defined]
            email=oauth_token.email,  # type: ignore[attr-defined]
            email_verified=oauth_token.email_verified,  # type: ignore[attr-defined]
            full_name=oauth_token.name.strip(),  # type: ignore[attr-defined]
        )
        user = UserController.create_user(session=session, user_create=user_in)
    return user


def _build_redirect_response(
    redirect_target: str,
    auth_code: str,
    access_token: str,
    refresh_token: str,
    access_delta: timedelta,
) -> RedirectResponse:
    """Build the redirect response with auth cookies."""
    response = RedirectResponse(url=f"{redirect_target}#auth_code={auth_code}")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=int(access_delta.total_seconds()),
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_COOKIE_EXPIRE_SECONDS,
    )
    return response


def _inc_oauth_metric(result: str) -> None:
    """Increment oauth_attempts_total counter for the Google provider."""
    _m = _get_metrics()
    if _m and _m.oauth_attempts_total:
        _m.oauth_attempts_total.labels(provider="google", result=result).inc()


def _build_auth_code_payload(
    user: object,
    access_token: str,
    access_delta: timedelta,
    code_challenge: str,
) -> tuple[str, str]:
    """Return (auth_code UUID, JSON payload) for the one-time auth code bridge."""
    expires_at_ms = int((datetime.now(timezone.utc) + access_delta).timestamp() * 1000)
    auth_code = str(_uuid.uuid4())
    auth_payload = json.dumps(
        {
            "version": 1,
            "auth_provider": "google",
            "access_token": access_token,
            "expires_at": expires_at_ms,
            "user": {
                # Bounded to prevent oversized Redis payloads / UI rendering issues.
                "name": (user.full_name or "")[:128],  # type: ignore[attr-defined]
                "email": (user.email or "")[:254],  # type: ignore[attr-defined]
                "avatar": (user.avatar or "")[:512],  # type: ignore[attr-defined]
            },
            "code_challenge": code_challenge,
        }
    )
    return auth_code, auth_payload


async def _perform_oauth_exchange(
    session: SessionDep,
    redis: object,
    code: str,
    code_verifier: str,
    callback_uri: str,
    redirect_target: str,
    code_challenge: str,
    state: str,
) -> RedirectResponse:
    """Exchange Google auth code for tokens, store auth_code, return redirect."""
    oauth_token = await OAuthController.get_google_access_token(
        code=code,
        code_verifier=code_verifier,
        redirect_uri=callback_uri,
    )
    user = _get_or_create_user(session, oauth_token)
    access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)
    access_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    AuthController.create_auth_session(
        session=session,
        user=user,
        jti=jti,
        refresh_token=refresh_token,
        external_token=ExternalTokensData(
            expires=oauth_token.expires_in,  # type: ignore[attr-defined]
            access=SecretStr(oauth_token.access_token),  # type: ignore[attr-defined]
            refresh=SecretStr(oauth_token.refresh_token),  # type: ignore[attr-defined]
        ),
    )
    if not settings.is_stateless:
        RedisRefreshStore(redis).register(jti, _REFRESH_TTL_SECONDS)  # type: ignore[arg-type]
    SessionController.purge_expired_sessions(session=session, current_user=user)
    auth_code, auth_payload = _build_auth_code_payload(
        user, access_token, access_delta, code_challenge
    )
    AuthCodeStore(redis).store(auth_code, auth_payload)  # type: ignore[arg-type]
    # Consume session only after auth_code is safely stored.
    OAuthSessionStore(redis).delete(state)  # type: ignore[arg-type]
    return _build_redirect_response(
        redirect_target, auth_code, access_token, refresh_token, access_delta
    )


@router.get("/oauth-callback/")
async def google_auth_callback(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
):
    """Handle Google OAuth2 callback: exchange code → issue auth_code → redirect extension.

    CSRF check: OAuthSessionStore.get(state) returning None is the CSRF guard.
    Uses get()+delete() NOT GETDEL — transient failures don't destroy the session.
    Delivers auth_code via URL fragment (#auth_code=) to avoid server/proxy logging.
    """
    try:
        redis = get_redis_client()
        if redis is None:
            raise HTTPException(
                status_code=503,
                detail="Cache service unavailable. Cannot complete OAuth flow.",
            )
        oauth_session = _get_oauth_session(redis, state)
        code_verifier: str = oauth_session.get("pkce_verifier", "")
        redirect_target: str = oauth_session.get("redirect_target", "")
        code_challenge: str = oauth_session.get("code_challenge", "")
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("OAuth session lookup failed: %s", ex)
        raise HTTPException(400, "Invalid state parameter") from ex

    # Use fixed config URI — never derived from request to prevent host-spoofing.
    callback_uri = settings.GOOGLE_OAUTH_REDIRECT_URI or str(
        request.url_for("google_auth_callback")
    )

    try:
        response = await _perform_oauth_exchange(
            session,
            redis,
            code,
            code_verifier,
            callback_uri,
            redirect_target,
            code_challenge,
            state,
        )
        _inc_oauth_metric("success")
        return response
    except HTTPXError as ex:
        logger.error("Google token exchange failed: %s", ex)
        _inc_oauth_metric("failed")
        raise HTTPException(
            status_code=400, detail="Token exchange with Google failed."
        ) from ex
    except HTTPException:
        raise
    except Exception as ex:
        logger.exception("Unexpected error during Google OAuth callback")
        _inc_oauth_metric("failed")
        raise HTTPException(status_code=500, detail="Authentication error.") from ex
