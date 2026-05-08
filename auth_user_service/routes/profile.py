"""Users routes"""

import uuid
from typing import Any
from os.path import join as PathJoin
from pathlib import Path
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError

from auth_user_service.core.config import settings
from auth_user_service.services.users import UserController
from auth_user_service.core.deps import CurrentUser, SessionDep
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import (
    UpdatePassword,
    UserPublic,
    UserUpdateMe,
)
from auth_user_service.schemas.user import ResponseUploadedAvatar, ResponseUser
from auth_user_service.utils.files import FilesHelper
from auth_sdk_m8.controllers.base import BaseController
from auth_sdk_m8.models.shared import Message

# pylint: disable=not-callable, broad-exception-caught

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post(
    "/upload_avatar/",
    response_model=ResponseUploadedAvatar,
    responses=BaseController.get_error_responses(),
)
def update_avatar(
    *, session: SessionDep, current_user: CurrentUser, file: UploadFile = File(...)
) -> Any:
    """
    Update own user.
    """
    try:
        if file.content_type not in FilesHelper.ALLOWED_IMG_MIME_TYPES:
            raise ValidationError(
                "Invalid file mime type. Allowed types are: "
                f"{', '.join(FilesHelper.ALLOWED_IMG_MIME_TYPES)}"
            )
        ext = FilesHelper.get_file_extension(file.filename)
        if ext not in FilesHelper.ALLOWED_IMG_EXTENSIONS:
            raise ValidationError(
                "Invalid file extension. Allowed extensions are: "
                f"{', '.join(FilesHelper.ALLOWED_IMG_EXTENSIONS)}"
            )
        contents = file.file.read(FilesHelper.MAX_IMG_FILE_SIZE + 1)
        if len(contents) > FilesHelper.MAX_IMG_FILE_SIZE:
            raise ValidationError(
                "File too large. Maximum allowed size is "
                f"{FilesHelper.MAX_IMG_FILE_SIZE} bytes"
            )
        file.file.seek(0)
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        file_path = PathJoin(
            Path(settings.STATIC_BASE_PATH), "avatars", unique_filename
        )

        with open(file_path, "wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                buffer.write(chunk)
        current_user.avatar = str(unique_filename)
        session.add(current_user)
        session.commit()
        return ResponseUploadedAvatar(
            success=True,
            msg=f"Successfully uploaded {file.filename}",
            avatar=unique_filename,
        )
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)
    finally:
        file.file.close()


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
        user_data = user_in.model_dump(exclude_unset=True)
        current_user.sqlmodel_update(user_data)
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        return ResponseUser(success=True, user=current_user)
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)


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
        if not SecurityHelper.verify_password(
            body.current_password, current_user.hashed_password
        ):
            raise HTTPException(status_code=400, detail="Incorrect password")
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=400,
                detail="New password cannot be the same as the current one",
            )
        hashed_password = SecurityHelper.get_password_hash(body.new_password)
        current_user.hashed_password = hashed_password
        session.add(current_user)
        session.commit()
        return Message(message="Password updated successfully")
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)


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
        session.delete(current_user)
        session.commit()
        return Message(message="User deleted successfully")
    except Exception as ex:
        return BaseController.handle_exception(ex=ex, session=session)
