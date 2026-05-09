"""Users routes"""

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select
from auth_user_service.services.users import UserController
from auth_user_service.core.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from auth_sdk_m8.models.shared import Message
from auth_user_service.db_models.sessions import ClientSession
from auth_user_service.db_models.users import (
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
)
from auth_sdk_m8.controllers.base import BaseController

# pylint: disable=not-callable, broad-exception-caught

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
    responses=BaseController.get_error_responses(),
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    try:
        count_statement = select(func.count()).select_from(User)
        count = session.exec(count_statement).one()

        statement = select(User).offset(skip).limit(limit)
        users = session.exec(statement).all()

        return UsersPublic(data=users, count=count)
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)


@router.post(
    "/new_user/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    responses=BaseController.get_error_responses(),
)
def create_new_user_with_password(*, session: SessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    try:
        user = UserController.get_user_by_email(session=session, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail=("The user with this email already exists in the system."),
            )

        user = UserController.create_user(session=session, user_create=user_in)
        return user
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)


@router.post(
    "/signup/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    responses=BaseController.get_error_responses(),
)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    try:
        user = UserController.get_user_by_email(session=session, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
        user_create = UserCreate.model_validate(user_in)
        user = UserController.create_user(session=session, user_create=user_create)
        return user
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)


@router.get(
    "/get/{user_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    responses=BaseController.get_error_responses(),
)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/update/{user_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
    responses=BaseController.get_error_responses(),
)
def update_current_user(
    *,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """
    try:
        db_user = session.get(User, user_id)
        if not db_user:
            raise HTTPException(
                status_code=404,
                detail="The user with this id does not exist in the system",
            )
        if user_in.email:
            existing_user = UserController.get_user_by_email(
                session=session, email=user_in.email
            )
            if existing_user and existing_user.id != user_id:
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )

        db_user = UserController.update_user(
            session=session, db_user=db_user, user_in=user_in
        )
        return db_user
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)


@router.delete(
    "/delete/{user_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    responses=BaseController.get_error_responses(),
)
def delete_user(
    session: SessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    try:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user == current_user:
            raise HTTPException(
                status_code=403,
                detail="Super users are not allowed to delete themselves",
            )
        statement = delete(ClientSession).where(col(ClientSession.user_id) == user_id)
        session.exec(statement)  # type: ignore
        session.delete(user)
        session.commit()
        return Message(message="User deleted successfully")
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)
