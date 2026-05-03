"""
Private API routes for inter-service user management.

These endpoints are NOT exposed to the public internet. They must be
protected at the network level (Docker internal network) AND require
the X-Internal-Token header to match PRIVATE_API_SECRET.
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from auth_user_service.core.deps import SessionDep, verify_private_api_secret
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import User, UserPublic

router = APIRouter(
    tags=["private"],
    prefix="/private",
    dependencies=[Depends(verify_private_api_secret)],
)


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
