"""Image upscaler schemas."""
from typing import Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from imgtools_m8.helpers.regex_patterns import ValidationConstants

UpscaleModelNames = Literal['edsr', 'espcn', 'fsrcnn', 'lapsrn']


class UpscaleModelDict(TypedDict):
    """Upscale Model Dict Type"""
    model_path: Optional[str] = Field(
        None,
        description='Path to upscaler model path.',
        pattern=ValidationConstants.FILE_PATH_REGEX.pattern
    )
    model_name: Optional[UpscaleModelNames] = Field(
        None,
        description='Name of the upscale model to use.'
    )
    scale: Optional[int] = Field(
        None, ge=1, le=8, description='Upscaler scale factor.'
    )


class UpscaleModelType(BaseModel):
    """Upscale Model Pydantic Type"""
    model_path: Optional[str] = Field(
        None,
        description='Path to upscaler model path.',
        pattern=ValidationConstants.FILE_PATH_REGEX.pattern
    )
    model_name: Optional[UpscaleModelNames] = Field(
        None,
        description='Name of the upscale model to use.'
    )
    scale: Optional[int] = Field(
        None, ge=1, le=8, description='Upscaler scale factor.'
    )

    class Config:
        """Pydantic Config"""
        extra = 'forbid'
        frozen = True

    def to_dict(self) -> UpscaleModelDict:
        """Convert to dictionary."""
        return self.model_dump()
