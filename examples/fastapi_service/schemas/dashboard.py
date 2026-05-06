"""
DashBoard Models
"""
# pylint: disable=W0718
from enum import Enum
from typing_extensions import TypedDict

from pydantic import BaseModel


class RangeActivityType(str, Enum):
    """
    Category type Enum
    """
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"


class ActivityCounter(TypedDict):
    """Activity Counter Dict Type"""
    model: str
    updated: int
    added: int


class ActivityStats(TypedDict):
    """Activity Stats Dict Type"""
    min: int
    max: int
    activity: list[ActivityCounter]


class UsersActivity(BaseModel):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    nb_users: int
    activity: ActivityStats


class FileItemStats(TypedDict):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    fina: int | str


class FilesStats(TypedDict):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    archives: FileItemStats
    emoncms: FileItemStats


class ModelsCountStats(BaseModel):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    nb_files: FilesStats
    file_sizes: FilesStats
    nb_paths: int
    nb_hosts: int
