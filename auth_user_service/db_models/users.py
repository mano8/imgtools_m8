"""
User-related database models and schemas.
These models define the structure of user data in the database and
the validation rules for user-related operations.
"""

from typing import List, Optional, TYPE_CHECKING
import uuid

from pydantic import EmailStr, ValidationError, field_validator, model_validator
from sqlalchemy import Column
from sqlmodel import Field, Relationship, SQLModel, Uuid

from auth_sdk_m8.schemas.base import AuthProviderType, RoleType
from auth_sdk_m8.models.shared import TimestampMixin
from auth_user_service.core.db_utils import get_table_args, prefixed_tables

if TYPE_CHECKING:
    from auth_user_service.db_models.api_keys import ApiKey, RateLimit
    from auth_user_service.db_models.sessions import ClientSession


def _check_avatar_url(v: object) -> object:
    """Reject non-URL avatar values; only http/https URLs accepted."""
    if v is None:
        return v
    if not isinstance(v, str):
        raise ValueError("avatar must be a string URL")
    if any(c.isspace() for c in v):
        raise ValueError("avatar URL must not contain whitespace")
    if not v.startswith(("http://", "https://")):
        raise ValueError("avatar must be an http:// or https:// URL")
    host_part = v.split("://", 1)[1].split("/")[0]
    if not host_part or host_part.startswith(("?", "#")):
        raise ValueError("avatar URL must include a valid host")
    return v


# ---------------------------------------------------------------
# ---------------------------------------------------------------
# ------- User
# ---------------------------------------------------------------
# ---------------------------------------------------------------
# Shared properties


class UserBase(TimestampMixin, SQLModel):
    """
    Shared fields for all User schemas.
    """

    provider: AuthProviderType = Field(
        default=AuthProviderType.PASSWORD,
        sa_column_kwargs={"nullable": False},
        description="Authentication provider type",
    )
    email: EmailStr = Field(
        max_length=255,
        sa_column_kwargs={"unique": True, "nullable": False, "index": True},
        description="User email address",
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User full name",
    )
    avatar: Optional[str] = Field(
        default=None,
        max_length=255,
        description="HTTP/HTTPS URL to user avatar image",
    )
    is_active: bool = Field(
        default=True,
        description="Flag indicating if the user account is active",
    )
    email_verified: bool = Field(
        default=False,
        description="Flag indicating if the user's email has been verified",
    )
    is_superuser: bool = Field(
        default=False,
        description="Flag for built-in superuser privileges",
    )
    role: RoleType = Field(
        default=RoleType.USER,
        description="Role assigned to the user for access control",
    )

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar_url(cls, v: object) -> object:
        """Reject non-URL avatar values; only http/https URLs accepted."""
        return _check_avatar_url(v)


class UserCreate(UserBase):
    """
    Schema for creating a new user.

    - PASSWORD provider requires `password` and disallows `oauth_user_id`.
    - GOOGLE provider requires `oauth_user_id` and disallows `password`.
    """

    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Plain-text password (hashed internally)",
    )
    oauth_user_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="OAuth provider user identifier",
    )

    @model_validator(mode="after")
    def check_provider_fields(self) -> "UserCreate":
        """
        Validates fields based on the `provider`:
        - If PASSWORD, ensures `password` is provided and `oauth_user_id` is None.
        - If GOOGLE, ensures `oauth_user_id` is provided and `password` is None.
        """
        if self.provider == AuthProviderType.PASSWORD:
            if not self.password:
                raise ValidationError(
                    [
                        {
                            "loc": ("password",),
                            "msg": "Password required for PASSWORD provider",
                            "type": "value_error.missing",
                        }
                    ],
                    model=type(self),
                )
            if self.oauth_user_id is not None:
                raise ValidationError(
                    [
                        {
                            "loc": ("oauth_user_id",),
                            "msg": "oauth_user_id must be None for PASSWORD provider",
                            "type": "value_error",
                        }
                    ],
                    model=type(self),
                )

        if self.provider == AuthProviderType.GOOGLE:
            if not self.oauth_user_id:
                raise ValidationError(
                    [
                        {
                            "loc": ("oauth_user_id",),
                            "msg": "oauth_user_id required for GOOGLE provider",
                            "type": "value_error.missing",
                        }
                    ],
                    model=type(self),
                )
            if self.password is not None:
                raise ValidationError(
                    [
                        {
                            "loc": ("password",),
                            "msg": "password must be None for GOOGLE provider",
                            "type": "value_error",
                        }
                    ],
                    model=type(self),
                )

        return self


class UserRegister(SQLModel):
    """
    Payload for new user self-registration.
    """

    email: EmailStr = Field(..., max_length=255, description="User email address")
    password: str = Field(
        ..., min_length=8, max_length=128, description="Plain-text password"
    )
    full_name: Optional[str] = Field(
        default=None, max_length=100, description="User full name"
    )


class UserUpdate(SQLModel):
    """
    Fields allowed for updating a user record.
    Pass current `provider` to enforce proper validation.
    """

    email: Optional[EmailStr] = Field(
        default=None,
        max_length=255,
        description="Updated email address",
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated user full name",
    )
    avatar: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Updated avatar URL",
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="New plain-text password (if provider=PASSWORD)",
    )
    oauth_user_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="OAuth provider user ID (if provider=GOOGLE)",
    )
    role: Optional[RoleType] = Field(
        default=None,
        description="New role for the user (admin only)",
    )
    provider: Optional[AuthProviderType] = None  # for validation context

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar_url(cls, v: object) -> object:
        """Reject non-URL avatar values; only http/https URLs accepted."""
        return _check_avatar_url(v)

    @model_validator(mode="after")
    def enforce_provider_rules(self) -> "UserUpdate":
        """
        Ensures fields align with the `provider`:
        - PASSWORD provider disallows `oauth_user_id`.
        - GOOGLE provider disallows `password`.
        """
        if (
            self.provider == AuthProviderType.PASSWORD
            and self.oauth_user_id is not None
        ):
            raise ValidationError(
                [
                    {
                        "loc": ("oauth_user_id",),
                        "msg": "Cannot set oauth_user_id on PASSWORD provider",
                        "type": "value_error",
                    }
                ],
                model=type(self),
            )

        if self.provider == AuthProviderType.GOOGLE and self.password is not None:
            raise ValidationError(
                [
                    {
                        "loc": ("password",),
                        "msg": "Cannot set password on GOOGLE provider",
                        "type": "value_error",
                    }
                ],
                model=type(self),
            )

        return self


class UserUpdateMe(SQLModel):
    """
    Payload allowing users to update their own profile fields.
    """

    email: Optional[EmailStr] = Field(
        default=None,
        max_length=255,
        description="Updated email address",
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Updated full name",
    )
    avatar: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Updated avatar URL",
    )

    @field_validator("avatar", mode="before")
    @classmethod
    def validate_avatar_url(cls, v: object) -> object:
        """Reject non-URL avatar values; only http/https URLs accepted."""
        return _check_avatar_url(v)


class UpdatePassword(SQLModel):
    """
    Schema for password change endpoint.
    """

    current_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Existing password to validate identity",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password to replace the existing one",
    )


class User(UserBase, table=True):
    """
    Database model representing a user record.
    Contains hashed credentials and relationships.
    """

    __tablename__ = prefixed_tables("user")
    __table_args__ = (get_table_args(),)
    id: uuid.UUID = Field(
        sa_column=Column(
            "id",
            Uuid(as_uuid=True),
            default=uuid.uuid4,
            primary_key=True,
            index=True,
        ),
        description="Unique user identifier (UUID)",
    )
    hashed_password: Optional[str] = Field(
        default=None,
        min_length=60,
        max_length=255,
        description="Bcrypt password hash",
    )
    oauth_user_id: Optional[str] = Field(
        default=None,
        unique=True,
        max_length=256,
        description="OAuth provider user ID",
    )
    telegram_id: Optional[str] = Field(
        default=None,
        unique=True,
        max_length=256,
        description="Telegram user ID",
    )
    api_keys: List["ApiKey"] = Relationship(
        back_populates="user",
    )
    rate_limits: List["RateLimit"] = Relationship(
        back_populates="user",
    )
    sessions: List["ClientSession"] = Relationship(
        back_populates="user",
    )


class UserPublic(UserBase):
    """
    Public representation of a user (safely excludes private fields).
    """

    id: uuid.UUID


class UsersPublic(SQLModel):
    """
    Wrapper for paginated user lists.
    """

    data: List[UserPublic] = Field(
        description="List of public user objects",
    )
    count: int = Field(
        description="Total number of users available",
    )
