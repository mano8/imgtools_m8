"""AddOn extension auth."""
import logging
from datetime import timedelta
from httpx import HTTPError as HTTPXError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import SecretStr

from auth_user_service.services.auth import AuthController
from auth_user_service.db_models.users import UserCreate
from auth_user_service.core.deps import SessionDep
from auth_user_service.services.client_sessions import SessionController
from auth_user_service.services.users import UserController
from auth_user_service.services.oauth import OAuthController
from auth_user_service.core.client import PKCEStore
from auth_user_service.core.deps import get_redis_client
from auth_user_service.core.config import settings

from auth_sdk_m8.schemas.auth import ExternalTokensData
from auth_sdk_m8.schemas.base import AuthProviderType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-auth", tags=["google-auth"])

_SECURE_COOKIE = settings.ENVIRONMENT != "local"


@router.get("/oauth-callback/")
async def google_auth_callback(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
):
    """
    Handle Google OAuth2 callback: exchange code for tokens,
    create or retrieve user, generate internal JWTs,
    persist session (internal + external tokens), and redirect.

    Args:
        code: OAuth2 authorization code from Google.
        session: DB session dependency.
        state: Anti-CSRF / PKCE state parameter.
    """
    try:
        pkce_store = PKCEStore(get_redis_client())
        code_verifier = pkce_store.pop(state)
        if not code_verifier:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired state parameter",
            )
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("PKCE state lookup failed: %s", ex)
        raise HTTPException(400, "Invalid state parameter") from ex

    try:
        oauth_token = await OAuthController.get_google_access_token(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=str(request.url_for("google_auth_callback")),
        )

        user = UserController.get_user_by_email(
            session=session,
            email=oauth_token.email,
        )
        if user is None:
            user_in = UserCreate(
                provider=AuthProviderType.GOOGLE,
                oauth_user_id=oauth_token.user_id,
                email=oauth_token.email,
                email_verified=oauth_token.email_verified,
                full_name=oauth_token.name.strip(),
            )
            user = UserController.create_user(session=session, user_create=user_in)

        access_token, refresh_token, jti = AuthController.create_auth_tokens(user=user)

        session_data = AuthController.create_auth_session(
            session=session,
            user=user,
            jti=jti,
            refresh_token=refresh_token,
            external_token=ExternalTokensData(
                expires=oauth_token.expires_in,
                access=SecretStr(oauth_token.access_token),
                refresh=SecretStr(oauth_token.refresh_token),
            ),
        )

        SessionController.purge_expired_sessions(
            session=session,
            current_user=user,
        )

        response = RedirectResponse(
            url=request.url_for(
                "google_auth_success_login", session_id=str(session_data.id)
            )
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=_SECURE_COOKIE,
            samesite="lax",
            max_age=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES).seconds,
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

    except HTTPXError as ex:
        logger.error("Google token exchange failed: %s", ex)
        raise HTTPException(
            status_code=400, detail="Token exchange with Google failed."
        ) from ex
    except HTTPException:
        raise
    except Exception as ex:
        logger.exception("Unexpected error during Google OAuth callback")
        raise HTTPException(status_code=500, detail="Authentication error.") from ex
