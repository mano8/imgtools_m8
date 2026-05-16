"""
Api key and rate limit models for the database.
These models are used to manage API keys and their associated rate limits.
"""

import uuid
from sqlalchemy import Uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlmodel import Column, Field, ForeignKey, Relationship, SQLModel

from auth_sdk_m8.schemas.base import Period
from auth_sdk_m8.models.shared import TimestampMixin
from auth_user_service.core.db_utils import (
    get_table_args,
    prefixed_fk,
    prefixed_tables,
)

if TYPE_CHECKING:
    from auth_user_service.db_models.users import User


# ---------------------------------------------------------------
# ---------------------- API KEY MODELS ------------------------
# ---------------------------------------------------------------
class ApiKeyBase(TimestampMixin, SQLModel):
    """
    Shared fields for API key schemas.
    """

    name: str = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Developer-defined key name",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"nullable": True},
        description="When the key expires (UTC)",
    )
    revoked: bool = Field(
        default=False,
        description="Whether the key is revoked",
    )


class ApiKeyCreate(SQLModel):
    """
    Schema for creating a new API key.
    """

    name: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Developer-friendly key name",
    )
    ttl_hours: int = Field(
        default=24,
        gt=0,
        description="Time to live for the key in hours",
    )


class ApiKey(ApiKeyBase, SQLModel, table=True):
    """
    Database model for storing API keys.
    """

    __tablename__ = prefixed_tables("api_key")
    __table_args__ = (get_table_args(),)
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        index=True,
        description="Unique API key ID",
    )
    key_hash: str = Field(
        sa_column_kwargs={"unique": True, "nullable": False},
        min_length=64,
        max_length=128,
        description="Secure hash of the API key",
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            "user_id",
            Uuid(as_uuid=True),
            ForeignKey(prefixed_fk("user", "id"), ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="Owner user ID",
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        description="Last time the key was used (UTC)",
    )

    user: "User" = Relationship(
        back_populates="api_keys",
    )


class ApiKeyPublic(ApiKeyBase, SQLModel):
    """
    Public representation of an API key (no key hash).
    """

    id: uuid.UUID = Field(
        description="Unique API key ID",
    )
    last_used_at: Optional[datetime] = Field(
        default=None,
        description="Last time the key was used (UTC)",
    )


# ---------------------------------------------------------------
# ---------------------- RATE LIMIT MODELS ---------------------
# ---------------------------------------------------------------
class RateLimit(SQLModel, table=True):
    """
    Database model for storing rate limit configurations per user.
    """

    __tablename__ = prefixed_tables("rate_limit")
    __table_args__ = (get_table_args(),)
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Rate limit record ID",
    )
    user_id: uuid.UUID = Field(
        sa_column=Column(
            "user_id",
            Uuid(as_uuid=True),
            ForeignKey(prefixed_fk("user", "id"), ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        description="User to whom the limit applies",
    )
    period: Period = Field(
        sa_column_kwargs={"nullable": False},
        description="Rate limit interval",
    )
    limit: int = Field(
        nullable=False,
        gt=0,
        description="Maximum requests allowed in the interval",
    )

    user: "User" = Relationship(
        back_populates="rate_limits",
    )
