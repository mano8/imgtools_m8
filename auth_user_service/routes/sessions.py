"""Sessions routes"""
import uuid
from typing import Any
from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)
from sqlmodel import (
    col,
    delete,
    func,
    select
)
from auth_sdk_m8.schemas.base import AuthProviderType
from auth_sdk_m8.models.shared import Message
from auth_sdk_m8.controllers.base import BaseController
from auth_user_service.core.config import settings
from auth_user_service.core.security import SecurityHelper
from auth_user_service.core.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from auth_user_service.db_models.sessions import (
    ClientSession,
    ClientSessionPublic,
    ClientSessionUpdateExternal,
    ClientSessionsPublic
)

# pylint: disable=not-callable, broad-exception-caught

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ClientSessionsPublic,
    responses=BaseController.get_error_responses()
)
def session_list(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """
    try:
        count_statement = select(func.count()).select_from(ClientSession)
        count = session.exec(count_statement).one()

        statement = select(ClientSession).offset(skip).limit(limit)
        users = session.exec(statement).all()

        return ClientSessionsPublic(data=users, count=count)
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )


@router.get(
    "/get/{session_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ClientSessionPublic,
    responses=BaseController.get_error_responses()
)
def get_session_by_id(
    session_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    try:
        client_session = session.get(ClientSession, session_id)
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
        return client_session
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )


@router.get(
    "/get-by-user/{user_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ClientSessionPublic,
    responses=BaseController.get_error_responses()
)
def get_session_by_user(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    try:
        statement = select(ClientSession).where(ClientSession.user_id == user_id)
        if not current_user.is_superuser:
            statement.where(ClientSession.user_id == current_user.id)
        client_session = session.exec(statement).first()
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
        return client_session
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )


@router.get(
    "/get-current/",
    response_model=ClientSessionPublic,
    responses=BaseController.get_error_responses()
)
def get_my_session(
    session: SessionDep,
    current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    try:
        statement = select(ClientSession).where(ClientSession.user_id == str(current_user.id))
        client_session = session.exec(statement).first()
        if client_session is None:
            raise HTTPException(
                status_code=400,
                detail="The user session unavelable",
            )
        return client_session
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )

@router.post(
    "/refresh-google-tokens/",
    response_model=ClientSessionPublic,
    responses=BaseController.get_error_responses()
)
def refresh_google_session_tokens(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    external_tokens: ClientSessionUpdateExternal
) -> Any:
    """
    Create new user.
    """
    try:
        statement = select(ClientSession).where(ClientSession.user_id == str(current_user.id))
        client_session = session.exec(statement).first()
        if client_session is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The user with this email already exists "
                    "in the system."),
            )
        if client_session.provider != AuthProviderType.GOOGLE:
            raise HTTPException(
                status_code=400,
                detail=(
                    "You need google api auth Provider."
                    f"Current is {str(client_session.provider)}"
                ),
            )

        enc_key = settings.TOKENS_ENCRYPTION_KEY.get_secret_value()
        client_session.external_access_token = (
            SecurityHelper.encrypt_token(external_tokens.external_access_token, enc_key)
            if external_tokens.external_access_token else None
        )
        client_session.external_refresh_token = (
            SecurityHelper.encrypt_token(external_tokens.external_refresh_token, enc_key)
            if external_tokens.external_refresh_token else None
        )
        client_session.external_token_expires_at = external_tokens.external_token_expires_at
        session.add(client_session)
        session.commit()
        session.refresh(client_session)
        return client_session
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )

@router.delete(
    "/delete-by-user/{user_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    responses=BaseController.get_error_responses()
)
def delete_sessions_by_user(
    session: SessionDep,
    user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    try:
        statement = delete(ClientSession).where(
            col(ClientSession.user_id) == user_id)
        session.exec(statement)  # type: ignore
        session.commit()
        return Message(message="User deleted successfully")
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )


@router.delete(
    "/delete/{session_id}/",
    dependencies=[Depends(get_current_active_superuser)],
    responses=BaseController.get_error_responses()
)
def delete_session(
    session: SessionDep,
    session_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    try:
        client_session = session.get(ClientSession, session_id)
        if not client_session:
            raise HTTPException(status_code=404, detail="Session not found")
        session.delete(client_session)
        session.commit()
        return Message(message="Session deleted successfully")
    except Exception as ex:
        return BaseController.handle_exception(
            ex=ex,
            session=session
        )
