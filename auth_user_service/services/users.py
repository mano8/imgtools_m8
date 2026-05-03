"""
Users Controller
"""
import uuid
from typing import Any
from sqlmodel import Session, select
from auth_user_service.core.security import SecurityHelper
from auth_user_service.db_models.users import (
    User,
    UserCreate,
    UserUpdate
)
from auth_sdk_m8.schemas.base import AuthProviderType


class UserController:
    """User Controller"""
    @staticmethod
    def create_user(
        *,
        session: Session,
        user_create: UserCreate
    ) -> User:
        """
        Create a new user in the database.

        Args:
            session (Session):
                The database session to use for the operation.
            user_create (UserCreate):
                An object containing the details of the user to be created.

        Returns:
            User: The newly created user object.

        Raises:
            SQLAlchemyError:
                If there is an error during the database operation.
        """
        if user_create.provider == AuthProviderType.PASSWORD:
            db_obj = User.model_validate(
                user_create,
                update={
                    "hashed_password": SecurityHelper.get_password_hash(
                        user_create.password),
                    "id": str(uuid.uuid4())
                }
            )
        else:
            db_obj = User.model_validate(
                user_create,
                update={"id": str(uuid.uuid4())})
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    @staticmethod
    def update_user(
        *,
        session: Session,
        db_user: User,
        user_in: UserUpdate
    ) -> Any:
        """
        Update an existing user in the database.

        Args:
            session (Session): The database session to use for the update.
            db_user (User): The existing user object to be updated.
            user_in (UserUpdate): The new data for the user.

        Returns:
            Any: The updated user object.

        Notes:
            - If the `user_in` contains a password, it will be hashed
            and stored in the `hashed_password` field.
            - The function commits the changes to the database
            and refreshes the `db_user` object.
        """
        user_data = user_in.model_dump(exclude_unset=True)
        extra_data = {}
        if "password" in user_data:
            password = user_data["password"]
            hashed_password = SecurityHelper.get_password_hash(password)
            extra_data["hashed_password"] = hashed_password
        db_user.sqlmodel_update(user_data, update=extra_data)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return db_user

    @staticmethod
    def get_user(*, session: Session, user_id: uuid.uuid4) -> User:
        """
        Retrieve a user from the database by their email address.

        Args:
            session (Session): The database session to use for the query.
            email (str): The email address of the user to retrieve.

        Returns:
            User | None: The user object if found, otherwise None.
        """
        statement = select(User).where(User.id == str(user_id))
        session_user = session.exec(statement).first()
        return session_user

    @staticmethod
    def get_user_by_email(*, session: Session, email: str) -> User:
        """
        Retrieve a user from the database by their email address.

        Args:
            session (Session): The database session to use for the query.
            email (str): The email address of the user to retrieve.

        Returns:
            User | None: The user object if found, otherwise None.
        """
        statement = select(User).where(User.email == email)
        session_user = session.exec(statement).first()
        return session_user

    @staticmethod
    def count_users(
        *,
        session: Session
    ) -> int:
        """
        Count users present.

        Args:
            session (Session): The database session to use for the query.

        Returns:
            int: Number of users in data base
        """
        statement = select(User)
        result = session.exec(statement).all()
        return len(result)
