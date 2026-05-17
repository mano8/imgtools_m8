"""API key management endpoints.

CRUD operations under /profile/api-keys — all require an authenticated user.
Key creation returns the plaintext once; subsequent reads show only metadata.
GET /verify accepts X-API-Key directly and enforces rate limits (no JWT needed).
"""

# pylint: disable=broad-exception-caught

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from auth_sdk_m8.controllers.base import BaseController
from auth_sdk_m8.models.shared import Message
from auth_sdk_m8.observability import metrics as _metrics
from auth_user_service.core.config import settings
from auth_user_service.core.deps import CurrentApiKey, CurrentUser, SessionDep
from auth_user_service.core.exceptions import handle_route_exception
from auth_user_service.db_models.api_keys import ApiKey, ApiKeyCreate, ApiKeyPublic
from auth_user_service.services.api_keys import ApiKeyService

router = APIRouter(prefix="/profile/api-keys", tags=["api-keys"])


class ApiKeyCreated(ApiKeyPublic):
    """Response model for key creation — includes plaintext shown exactly once."""

    plaintext: str


@router.get(
    "/verify",
    response_model=ApiKeyPublic,
    summary="Verify an API key and enforce rate limits",
)
def verify_api_key(api_key: CurrentApiKey) -> Any:
    """Validate the ``X-API-Key`` header and return the key's public metadata.

    Rate limits are enforced; ``X-RateLimit-*`` headers are always present when
    Redis is available. Returns 429 when the rate limit is exceeded.
    """
    return api_key


@router.post(
    "/",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    responses=BaseController.get_error_responses(),
)
def create_api_key(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: ApiKeyCreate,
) -> Any:
    """Create a new API key for the authenticated user.

    The plaintext key is returned exactly once and never stored.
    """
    try:
        stmt = select(ApiKey).where(
            ApiKey.user_id == current_user.id,
            col(ApiKey.revoked).is_(False),
        )
        active_count = len(session.exec(stmt).all())
        if active_count >= settings.API_KEY_MAX_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Maximum of {settings.API_KEY_MAX_PER_USER} active API keys reached. "
                    "Revoke an existing key before creating a new one."
                ),
            )

        plaintext, key_hash = ApiKeyService.generate_key()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=body.ttl_hours)

        api_key = ApiKey(
            name=body.name or f"key-{uuid.uuid4().hex[:8]}",
            key_hash=key_hash,
            user_id=current_user.id,
            expires_at=expires_at,
        )
        session.add(api_key)
        session.commit()
        session.refresh(api_key)

        m = _metrics.get()
        if m and m.api_key_lifecycle_total:
            m.api_key_lifecycle_total.labels(action="created").inc()

        return ApiKeyCreated(**api_key.model_dump(), plaintext=plaintext)
    except HTTPException:
        raise
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)


@router.get(
    "/",
    response_model=list[ApiKeyPublic],
    responses=BaseController.get_error_responses(),
)
def list_api_keys(
    *,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """List all API keys belonging to the authenticated user."""
    try:
        stmt = select(ApiKey).where(ApiKey.user_id == current_user.id)
        keys = session.exec(stmt).all()
        return keys
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)


@router.get(
    "/{key_id}",
    response_model=ApiKeyPublic,
    responses=BaseController.get_error_responses(),
)
def get_api_key(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    key_id: uuid.UUID,
) -> Any:
    """Get metadata for a single API key owned by the authenticated user."""
    try:
        api_key = session.get(ApiKey, key_id)
        if api_key is None or api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )
        return api_key
    except HTTPException:
        raise
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)


@router.delete(
    "/{key_id}",
    response_model=Message,
    responses=BaseController.get_error_responses(),
)
def revoke_api_key(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    key_id: uuid.UUID,
) -> Any:
    """Revoke an API key. Revoked keys are rejected on next use."""
    try:
        api_key = session.get(ApiKey, key_id)
        if api_key is None or api_key.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
            )
        if api_key.revoked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="API key is already revoked",
            )
        api_key.revoked = True
        session.add(api_key)
        session.commit()

        m = _metrics.get()
        if m and m.api_key_lifecycle_total:
            m.api_key_lifecycle_total.labels(action="revoked").inc()

        return Message(message="API key revoked successfully")
    except HTTPException:
        raise
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)
