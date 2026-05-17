"""
Api key and rate limit models for the database.
These models are used to manage API keys and their associated rate limits.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy import Uuid
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
    """Shared fields for API key schemas."""

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
    """Schema for creating a new API key."""

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
    """Database model for storing API keys."""

    __tablename__ = prefixed_tables("api_key")
    __table_args__ = (get_table_args(),)

    id: uuid.UUID = Field(
        sa_column=Column(
            "id",
            Uuid(as_uuid=True),
            default=uuid.uuid4,
            primary_key=True,
            index=True,
        ),
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

    user: "User" = Relationship(back_populates="api_keys")
    rate_limits: List["RateLimit"] = Relationship(back_populates="api_key")


class ApiKeyPublic(ApiKeyBase, SQLModel):
    """Public representation of an API key (no key hash)."""

    id: uuid.UUID = Field(description="Unique API key ID")
    last_used_at: Optional[datetime] = Field(
        default=None,
        description="Last time the key was used (UTC)",
    )


# ---------------------------------------------------------------
# ---------------------- RATE LIMIT MODELS ---------------------
# ---------------------------------------------------------------
class RateLimit(SQLModel, table=True):
    """
    Rate limit configuration.

    Enforcement priority: api_key_id row > user_id row > settings defaults.
    Invariant: at least one of api_key_id or user_id must be set (DB CHECK).
    """

    __tablename__ = prefixed_tables("rate_limit")
    __table_args__ = (
        sa.CheckConstraint(
            "api_key_id IS NOT NULL OR user_id IS NOT NULL",
            name="ck_ratelimit_has_owner",
        ),
        sa.UniqueConstraint(
            "api_key_id", "period", name="uq_ratelimit_api_key_period"
        ),
        sa.UniqueConstraint(
            "user_id", "period", name="uq_ratelimit_user_period"
        ),
        get_table_args(),
    )

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Rate limit record ID",
    )
    api_key_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            "api_key_id",
            Uuid(as_uuid=True),
            ForeignKey(prefixed_fk("api_key", "id"), ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        description="API key this limit applies to (primary enforcement axis)",
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            "user_id",
            Uuid(as_uuid=True),
            ForeignKey(prefixed_fk("user", "id"), ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        description="User default limit (fallback when no per-key override exists)",
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

    api_key: Optional["ApiKey"] = Relationship(back_populates="rate_limits")
    user: Optional["User"] = Relationship(back_populates="rate_limits")
