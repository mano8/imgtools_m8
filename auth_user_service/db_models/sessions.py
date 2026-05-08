"""
Client session models for managing user sessions and tokens.
This module defines the database models and schemas for client sessions,
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
import uuid
from sqlmodel import Column, Field, ForeignKey, Relationship, SQLModel
from auth_sdk_m8.schemas.base import AuthProviderType
from auth_sdk_m8.models.shared import TimestampMixin
from auth_user_service.core.db_utils import (
    UUIDChar,
    get_table_args,
    prefixed_fk,
    prefixed_tables,
)

if TYPE_CHECKING:
    from auth_user_service.db_models.users import User


# ---------------------------------------------------------------
# ---------------------- SESSION MODELS ------------------------
# ---------------------------------------------------------------
class ClientSessionBase(TimestampMixin, SQLModel):
    """
    Shared fields for session schemas, now including both
    internal (JWT) and external (Google) token tracking.
    """

    provider: AuthProviderType = Field(
        sa_column_kwargs={"nullable": False},
        description="Login provider for this session",
    )
    jwt_jti: str = Field(
        sa_column_kwargs={"nullable": False},
        min_length=16,
        max_length=128,
        description="Internal JWT unique identifier (JTI)",
    )
    refresh_token_hash: str = Field(
        sa_column_kwargs={"nullable": False},
        min_length=64,
        max_length=128,
        description="Hash of the internal refresh token",
    )
    jwt_expires_at: datetime = Field(
        nullable=False,
        description="Internal JWT expiration timestamp (UTC)",
    )
    refresh_expires_at: datetime = Field(
        nullable=False,
        description="Internal refresh token expiration timestamp (UTC)",
    )

    revoked: bool = Field(
        default=False,
        sa_column_kwargs={"nullable": False},
        description="Whether this session has been manually revoked",
    )

    # **External (Google) tokens**
    external_access_token: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Google OAuth access token",
    )
    external_refresh_token: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Google OAuth refresh token",
    )
    external_token_expires_at: Optional[datetime] = Field(
        default=None,
        description="Google OAuth token expiration timestamp (UTC)",
    )


class ClientSessionCreate(SQLModel):
    """
    Input schema for creating a new client session,
    now accepting external Google tokens too.
    """

    jwt_jti: str = Field(
        sa_column_kwargs={"nullable": False},
        min_length=16,
        max_length=128,
        description="Internal JWT ID (JTI)",
    )
    refresh_token_hash: str = Field(
        sa_column_kwargs={"nullable": False},
        min_length=64,
        max_length=128,
        description="Hash of internal refresh token",
    )
    jwt_expires_at: datetime = Field(
        nullable=False,
        description="Internal JWT expiration",
    )
    refresh_expires_at: datetime = Field(
        nullable=False,
        description="Internal refresh token expiration",
    )
    external_access_token: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Google OAuth access token",
    )
    external_refresh_token: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Google OAuth refresh token",
    )
    external_token_expires_at: Optional[datetime] = Field(
        default=None,
        description="Google OAuth token expiration",
    )


class ClientSessionUpdateExternal(SQLModel):
    """
    Input schema for creating a new client session,
    now accepting external Google tokens too.
    """

    external_access_token: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Google OAuth access token",
    )
    external_refresh_token: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Google OAuth refresh token",
    )
    external_token_expires_at: Optional[datetime] = Field(
        default=None,
        description="Google OAuth token expiration",
    )


class ClientSession(ClientSessionBase, SQLModel, table=True):
    """
    Database model for storing user sessions with full token metadata.
    """

    __tablename__ = prefixed_tables("client_session")
    __table_args__ = (get_table_args(),)
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        index=True,
        description="ClientSession ID",
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            "user_id",
            UUIDChar(),
            ForeignKey(prefixed_fk("user", "id"), ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="Owner user ID",
    )

    user: "User" = Relationship(
        back_populates="sessions",
    )


class ClientSessionPublic(ClientSessionBase, SQLModel):
    """
    Public representation of a session (no token hashes).
    """

    id: uuid.UUID = Field(description="ClientSession ID")


class ClientSessionsPublic(SQLModel):
    """
    Container model for multiple public item representations.

    Attributes:
        data (list[LoginClientSessionPublic]): List of public item models.
        count (int): Total count of items.
    """

    data: list[ClientSession]
    count: int
