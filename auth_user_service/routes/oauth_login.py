"""Google OAuth2 native-app bridge — JSON-only endpoints.

Two endpoints:
  GET  /google-api/login-url/  — initiate OAuth, returns Google auth URL
  POST /google-api/exchange/   — one-time auth code exchange for tokens
"""

import base64
import hashlib
import hmac
import json
import logging
import re
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from urllib.parse import urlparse

from auth_user_service.core.client import (
    AuthCodeStore,
    ExchangeRateLimiter,
    OAuthSessionStore,
)
from auth_user_service.core.config import settings
from auth_user_service.core.deps import get_redis_client
from auth_user_service.services.auth import AuthController
from auth_sdk_m8.observability.metrics import get as _get_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-api", tags=["google-api"])

# RFC 7636 §4.1 code_challenge (S256, base64url, 43-128 chars).
_CHALLENGE_RE = re.compile(r"[A-Za-z0-9\-_]{43,128}")
# RFC 7636 §4.1 code_verifier (unreserved chars, 43-128 chars).
_VERIFIER_RE = re.compile(r"[A-Za-z0-9\-._~]{43,128}")
# Hard-rejected web origin schemes — auth_code must never reach a server-logged URL.
_WEB_SCHEMES = {"http://", "https://"}
# Maximum sizes for defensive payload caps.
_SESSION_PAYLOAD_MAX = 4096
_AUTH_CODE_PAYLOAD_MAX = 8192


def _build_cors_origin_regex(schemes: list[str]) -> str | None:
    """Build a CORSMiddleware-compatible regex from scheme list (chrome-extension only)."""
    if not schemes:
        return None
    parts = []
    for s in schemes:
        if s == "chrome-extension://":
            parts.append(r"chrome-extension://[a-z]{32}")
        else:
            return None
    return f"^(?:{'|'.join(parts)})$"


def _verify_pkce(verifier: str, challenge: str) -> bool:
    """Return True if S256 PKCE verifier matches challenge.

    Uses hmac.compare_digest for constant-time comparison so timing cannot
    distinguish a wrong verifier from other failure modes.
    """
    digest = hashlib.sha256(verifier.encode()).digest()
    computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return hmac.compare_digest(computed, challenge)


def _validate_redirect_target(redirect_target: str) -> None:
    """Validate redirect_target string, scheme, and prefix restrictions."""
    if not redirect_target:
        raise HTTPException(status_code=400, detail="redirect_target is required.")
    if len(redirect_target) > 2048:
        raise HTTPException(status_code=400, detail="redirect_target too long.")

    parsed = urlparse(redirect_target)
    scheme = f"{parsed.scheme}://"

    if scheme in _WEB_SCHEMES:
        raise HTTPException(
            status_code=400,
            detail="redirect_target scheme not allowed: web origins are not permitted.",
        )
    if scheme not in settings.OAUTH_ALLOWED_REDIRECT_SCHEMES:
        raise HTTPException(
            status_code=400, detail="redirect_target scheme not allowed."
        )
    if not parsed.netloc:
        raise HTTPException(
            status_code=400, detail="redirect_target must include a host."
        )
    if settings.OAUTH_ALLOWED_REDIRECT_PREFIXES and not _uri_prefix_match_any(
        redirect_target, settings.OAUTH_ALLOWED_REDIRECT_PREFIXES
    ):
        raise HTTPException(
            status_code=400, detail="redirect_target not in allowed prefixes."
        )


def _build_session_payload(
    pkce_verifier: str, redirect_target: str, code_challenge: str
) -> str:
    """Serialise OAuth session payload and guard against oversized values."""
    payload = json.dumps(
        {
            "pkce_verifier": pkce_verifier,
            "redirect_target": redirect_target,
            "code_challenge": code_challenge,
            "created_at": int(datetime.now(timezone.utc).timestamp()),
            "flow": "google",
        }
    )
    if len(payload) > _SESSION_PAYLOAD_MAX:
        raise HTTPException(status_code=400, detail="Session payload too large.")
    return payload


@router.get("/login-url/")
async def get_google_login_url(
    redirect_target: str = "",
    code_challenge: str = "",
) -> dict[str, str]:
    """Return a Google OAuth2 authorization URL for the native-app flow.

    The caller must supply a ``redirect_target`` (URI where the browser will be
    redirected after Google consent) and a ``code_challenge`` (extension-side
    S256 PKCE challenge).  The backend stores a unified session payload under
    the OAuth ``state`` key and returns the Google auth URL.

    Security:
    - ``redirect_target`` scheme must be in ``OAUTH_ALLOWED_REDIRECT_SCHEMES``
      (default ``chrome-extension://``).
    - ``http://`` and ``https://`` are hard-rejected regardless of config.
    - The extension is a public OAuth client; scheme-only validation is
      intentional.  Set ``OAUTH_ALLOWED_REDIRECT_PREFIXES`` to restrict to
      specific extension IDs.
    """
    _validate_redirect_target(redirect_target)
    if not code_challenge:
        raise HTTPException(status_code=400, detail="code_challenge is required.")
    if not _CHALLENGE_RE.fullmatch(code_challenge):
        raise HTTPException(status_code=400, detail="code_challenge format invalid.")

    redis = get_redis_client()
    if redis is None:
        raise HTTPException(status_code=503, detail="Cache service unavailable.")

    callback_uri = settings.GOOGLE_OAUTH_REDIRECT_URI or None
    url, state, pkce_verifier = AuthController.get_google_login_url(
        redirect_uri=callback_uri
    )

    session_payload = _build_session_payload(
        pkce_verifier, redirect_target, code_challenge
    )
    OAuthSessionStore(redis).store(state, session_payload)
    return {"url": url}


def _uri_prefix_match_any(target: str, prefixes: list[str]) -> bool:
    """Return True if *target* is under any of the given URI prefixes.

    Uses netloc equality (not startswith) to prevent crafted netloc bypass
    e.g. ``chrome-extension://abc123.evil.com/`` passing a raw-string prefix
    check against ``chrome-extension://abc123``.
    """
    t = urlparse(target)
    t_path = t.path if t.path.endswith("/") else t.path + "/"
    for prefix in prefixes:
        p = urlparse(prefix)
        p_path = p.path.rstrip("/") + "/"
        if t.scheme == p.scheme and t.netloc == p.netloc and t_path.startswith(p_path):
            return True
    return False


class ExchangeRequest(BaseModel):
    code: str
    code_verifier: str
    client_hint: str | None = Field(default=None, max_length=128)


def _check_exchange_origin(request: Request) -> None:
    """Opportunistic Origin check — not a security gate (PKCE is the control).

    Rejects unexpected origins when CORS scheme allowlist is explicitly
    configured.
    """
    origin = request.headers.get("origin", "")
    if not origin or not settings.CORS_ALLOWED_ORIGIN_SCHEMES:
        return
    cors_regex = _build_cors_origin_regex(settings.CORS_ALLOWED_ORIGIN_SCHEMES)
    if cors_regex and not re.fullmatch(cors_regex, origin):
        logger.warning("exchange: unexpected Origin header: %s", origin)
        raise HTTPException(status_code=400, detail="Origin not allowed.")


def _pop_auth_code_payload(redis: object, code: str) -> dict:
    """Pop auth code from store, validate size, parse JSON and return payload."""
    raw = AuthCodeStore(redis).pop(code)  # type: ignore[arg-type]
    if not raw:
        _inc_exchange_metric("expired_or_invalid")
        raise HTTPException(status_code=400, detail="Invalid or expired auth code.")
    if len(raw) > _AUTH_CODE_PAYLOAD_MAX:
        _inc_exchange_metric("expired_or_invalid")
        raise HTTPException(status_code=400, detail="Invalid or expired auth code.")
    return json.loads(raw)


@router.post("/exchange/")
async def exchange_auth_code(
    request: Request,
    body: ExchangeRequest,
) -> dict:
    """Exchange a one-time auth code for tokens.

    The ``code`` was delivered via URL fragment to the extension's
    ``redirect_target`` after a successful Google OAuth callback.  This
    endpoint atomically pops the code from Redis (GETDEL) and verifies the
    extension-supplied PKCE ``code_verifier`` against the challenge that was
    bound to the code at login-initiation time.

    Rate-limited to 10 requests/minute per client IP to prevent Redis
    amplification from probe traffic.
    """
    client_ip = request.client.host if request.client else "unknown"

    redis = get_redis_client()
    if redis is None:
        _inc_exchange_metric("redis_unavailable")
        raise HTTPException(status_code=503, detail="Cache service unavailable.")

    if not ExchangeRateLimiter(redis).is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests.")

    if not _VERIFIER_RE.fullmatch(body.code_verifier):
        raise HTTPException(status_code=400, detail="code_verifier format invalid.")

    try:
        _uuid.UUID(body.code)
    except ValueError:
        _inc_exchange_metric("expired_or_invalid")
        raise HTTPException(status_code=400, detail="Invalid or expired auth code.")

    _check_exchange_origin(request)

    payload = _pop_auth_code_payload(redis, body.code)

    if not _verify_pkce(body.code_verifier, payload.get("code_challenge", "")):
        _inc_exchange_metric("pkce_failed")
        raise HTTPException(status_code=400, detail="PKCE verification failed.")

    if body.client_hint:
        logger.debug("exchange: client_hint=%s", body.client_hint)

    _inc_exchange_metric("success")
    return {k: v for k, v in payload.items() if k != "code_challenge"}


def _inc_exchange_metric(result: str) -> None:
    m = _get_metrics()
    if m and m.auth_code_exchange_total:
        m.auth_code_exchange_total.labels(result=result).inc()
