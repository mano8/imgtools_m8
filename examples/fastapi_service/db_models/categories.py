from typing import List
import uuid
from pydantic import model_validator
from sqlalchemy import UniqueConstraint
from sqlmodel import CHAR, Column, Field, SQLModel
from slugify import slugify

from auth_sdk_m8.schemas.base import CategoryType
from auth_sdk_m8.models.shared import TimestampMixin
from fastapi_service.core.db_models import prefixed_tables
from fastapi_service.core.config import settings


# ---------------------------------------------------------------
# ---------------------------------------------------------------
# ------- Category
# ---------------------------------------------------------------
# ---------------------------------------------------------------
class CategoryBase(SQLModel):
    """
    Shared fields for category schemas.
    """

    name: str = Field(
        unique=True,
        min_length=1,
        max_length=50,
        description="Category name",
    )
    slug: str = Field(
        unique=True,
        min_length=1,
        max_length=50,
        description="URL-friendly identifier",
    )
    type: CategoryType = Field(
        sa_column_kwargs={"nullable": False},
        description="Category type",
    )


class CategoryGenerators(CategoryBase):
    """
    Category schema with slug auto-generation.
    """

    @model_validator(mode="before")
    @classmethod
    def generate_slug(cls, values):
        """
        Auto-generate `slug` from the `name` field.
        """
        name = values.get("name")
        if name:
            values["slug"] = slugify(values.get("name"))
        return values


class CategoryCreate(CategoryGenerators):
    """
    Schema for creating a new category.
    """


class CategoryUpdate(CategoryGenerators):
    """
    Schema for updating an existing category.
    """


class Category(TimestampMixin, CategoryBase, SQLModel, table=True):
    """
    Database model for a category.
    """

    __tablename__ = prefixed_tables("category")
    __table_args__ = (
        UniqueConstraint("slug", name="uq_category_slug"),
        {"mysql_engine": settings.DB_ENGINE, "mysql_charset": settings.DB_CHARSET},
    )
    id: int = Field(
        default=None,
        primary_key=True,
        index=True,
        description="Category ID",
    )
    owner_id: uuid.UUID = Field(
        sa_column=Column("owner_id", CHAR(36), nullable=False, index=True),
        description="ID of the user who owns this category",
    )


class CategoryPublic(CategoryBase, SQLModel):
    """
    Public representation of a category.
    """

    id: int = Field(
        description="Category ID",
    )
    owner_id: uuid.UUID = Field(
        description="ID of the user who owns this category",
    )


class CategoriesPublic(SQLModel):
    """
    Wrapper for a list of public categories.
    """

    data: List[CategoryPublic] = Field(
        description="List of categories",
    )
    count: int = Field(
        description="Total categories count",
    )
