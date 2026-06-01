"""Users routes"""

from typing import Any
from fastapi import APIRouter, HTTPException

from auth_user_service.services.users import UserController
from auth_user_service.core.deps import CurrentUser, SessionDep
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import (
    UpdatePassword,
    User,
    UserPublic,
    UserUpdateMe,
)
from auth_user_service.schemas.user import ResponseUser
from auth_sdk_m8.controllers.base import BaseController
from auth_sdk_m8.models.shared import Message
from auth_user_service.core.exceptions import handle_route_exception

# pylint: disable=not-callable, broad-exception-caught

router = APIRouter(prefix="/profile", tags=["profile"])


@router.patch(
    "/update/me/",
    response_model=ResponseUser,
    responses=BaseController.get_error_responses(),
)
def update_user_me(
    *, session: SessionDep, current_user: CurrentUser, user_in: UserUpdateMe
) -> Any:
    """
    Update own user.
    """

    try:
        if user_in.email:
            existing_user = UserController.get_user_by_email(
                session=session, email=user_in.email
            )
            if existing_user and existing_user.id != current_user.id:
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )
        db_user = session.get(User, current_user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = user_in.model_dump(exclude_unset=True)
        for field, value in user_data.items():
            if field in set(type(db_user).model_fields):
                setattr(db_user, field, value)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return ResponseUser(success=True, user=db_user)
    except HTTPException:
        raise
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)


@router.patch(
    "/me/password/",
    response_model=Message,
    responses=BaseController.get_error_responses(),
)
def update_password_me(
    *, session: SessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    try:
        db_user = session.get(User, current_user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if not db_user.hashed_password or not SecurityHelper.verify_password(
            body.current_password, db_user.hashed_password
        ):
            raise HTTPException(status_code=400, detail="Incorrect password")
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=400,
                detail="New password cannot be the same as the current one",
            )
        db_user.hashed_password = SecurityHelper.get_password_hash(body.new_password)
        session.add(db_user)
        session.commit()
        return Message(message="Password updated successfully")
    except HTTPException:
        raise
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)


@router.get("/get/me/", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete(
    "/delete/me/",
    response_model=Message,
    responses=BaseController.get_error_responses(),
)
def delete_user_me(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    try:
        if current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="Super users are not allowed to delete themselves",
            )
        db_user = session.get(User, current_user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        session.delete(db_user)
        session.commit()
        return Message(message="User deleted successfully")
    except HTTPException:
        raise
    except Exception as ex:
        return handle_route_exception(ex=ex, session=session)
