"""Google Views routes."""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select

from auth_user_service.services.client_sessions import SessionController
from auth_user_service.core.security import SecurityHelper
from auth_user_service.services.auth import AuthController
from auth_user_service.db_models.sessions import ClientSession
from auth_user_service.core.deps import SessionDep, get_templates
from auth_user_service.core.config import settings

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.auth import TokenDecodeProps

router = APIRouter(prefix="/google-api", tags=["google-api"])
# pylint: disable=broad-exception-caught, not-callable


@router.get("/login/", response_class=HTMLResponse)
async def google_auth_login(
    request: Request, templates: Jinja2Templates = Depends(get_templates)
) -> dict:
    """Render the Google login page with the appropriate login URL."""
    google_login_url = AuthController.get_google_login_url(
        redirect_uri=str(request.url_for("google_auth_callback")),
    )
    context = {
        "request": request,
        "base_url": str(request.base_url),
        "google_login_url": google_login_url,
    }
    return templates.TemplateResponse("auth/login.html", context)


@router.get("/login_success/{session_id}/", response_class=HTMLResponse)
async def google_auth_success_login(
    response: Response,
    request: Request,
    session: SessionDep,
    session_id: uuid.UUID,
    access_token: str = Depends(SecurityHelper.get_access_token_from_cookie),
    templates: Jinja2Templates = Depends(get_templates),
) -> dict:
    """Render the Google login success page."""
    try:
        token_data = SecurityHelper.decode_access_token(
            token_data=TokenDecodeProps(
                access_token=access_token,
                secret_key=settings.ACCESS_SECRET_KEY,
                algorithm=settings.TOKEN_ALGORITHM,
            )
        )
    except InvalidToken as err:
        raise HTTPException(status_code=401, detail=str(err)) from err

    if SessionController.is_session_revoked(token_data.jti):
        response.delete_cookie(key="access_token")
        raise HTTPException(status_code=401, detail="Token revoked")

    statement = (
        select(ClientSession)
        .where(token_data.sub == ClientSession.user_id)
        .where(session_id == ClientSession.id)
    )
    current_session = session.exec(statement).first()

    if not current_session or current_session.refresh_expires_at < datetime.now(
        timezone.utc
    ).replace(tzinfo=None):
        raise HTTPException(status_code=403, detail="Session expired or invalid.")
    access_delta, refresh_delta = AuthController.get_tokens_expire()
    access_token, refresh_token, jti = AuthController.create_auth_tokens(
        user=current_session.user
    )

    current_session.jwt_expires_at = datetime.now(timezone.utc) + access_delta
    current_session.refresh_expires_at = datetime.now(timezone.utc) + refresh_delta
    current_session.jwt_jti = jti
    current_session.refresh_token_hash = SecurityHelper.hash_token(refresh_token)
    session.add(current_session)
    session.commit()
    context = {
        "request": request,
        "base_url": str(request.base_url),
        "session_id": str(session_id),
        "jwt": access_token,
        "jwt_expires": access_delta.seconds * 1000,
        "name": current_session.user.full_name or "User",
        "extension_id": settings.EXTENSION_ID,
    }
    return templates.TemplateResponse("auth/login_success.html", context)
