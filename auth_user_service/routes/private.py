"""
Private API routes for inter-service user management.

These endpoints are NOT exposed to the public internet. They must be
protected at the network level (Docker internal network) AND require
the X-Internal-Token header to match PRIVATE_API_SECRET.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from auth_user_service.core.config import settings
from auth_user_service.core.deps import (
    SessionDep,
    get_redis_client,
    verify_private_api_secret,
)
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import User, UserPublic

router = APIRouter(
    tags=["private"],
    prefix="/private",
    dependencies=[Depends(verify_private_api_secret)],
)


class JtiStatusRequest(BaseModel):
    """Request body for the inter-service JTI status check."""

    jti: str = Field(min_length=1)


class JtiStatusResponse(BaseModel):
    """Response for the inter-service JTI status check."""

    active: bool


class PrivateUserCreate(BaseModel):
    """Private Create user"""

    email: EmailStr
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user (internal service call only).
    """
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=SecurityHelper.get_password_hash(user_in.password),
    )
    session.add(user)
    session.commit()
    return user


@router.post(
    "/v1/jti-status",
    response_model=JtiStatusResponse,
    include_in_schema=False,
)
async def check_jti_status(
    body: JtiStatusRequest,
    redis=Depends(get_redis_client),
) -> JtiStatusResponse:
    """Check whether a JTI has been blacklisted (inter-service use only).

    Only meaningful when TOKEN_MODE=stateful. In hybrid/stateless modes no
    access token blacklist exists — returns active=True immediately.
    When Redis is unavailable the response honours ACCESS_REVOCATION_FAILURE_MODE:
    fail_closed → active=False (token treated as revoked, consumer returns 503);
    fail_open → active=True (token passes, legacy behaviour).
    Consumer services call this instead of accessing auth Redis directly.
    """
    if not settings.is_stateful:
        return JtiStatusResponse(active=True)
    if redis is None:
        mode = settings.effective_failure_mode("access_revocation")
        return JtiStatusResponse(active=(mode != "fail_closed"))
    from auth_sdk_m8.security import AccessTokenBlacklist  # noqa: PLC0415

    return JtiStatusResponse(
        active=not AccessTokenBlacklist(redis).is_revoked(body.jti)
    )
