"""
Schemas for Pillow-compatible output format optimizations in imgtools_m8.
"""

from enum import Enum
from typing import Optional, Union, List

from pydantic import BaseModel, Field, field_validator
from imgtools_m8.helpers.regex_patterns import ValidationConstants


class OutputFormatsEnum(str, Enum):
    """Enumeration of supported output formats."""
    JPEG = "jpeg"
    WEBP = "webp"
    PNG = "png"
    GIF = "gif"
    AVIF = "avif"


class OutputFormatBaseModel(BaseModel):
    """Base schema with format name."""
    name: OutputFormatsEnum = Field(..., description="Output format")


class JPEGFormat(OutputFormatBaseModel):
    """JPEG output format options compatible with Pillow."""
    name: OutputFormatsEnum = OutputFormatsEnum.JPEG
    quality: int = Field(
        95,
        ge=1,
        le=100,
        description="JPEG quality (1-100)"
    )
    optimize: bool = Field(
        True,
        description="Enable Huffman table optimization"
    )
    progressive: bool = Field(
        True,
        description="Use progressive JPEG encoding"
    )
    subsampling: Union[int, str] = Field(
        "4:2:0",
        description=(
            "Chroma subsampling: 0, 1, 2 or '4:4:4', '4:2:2', '4:2:0'. "
            "Controls color resolution."
        )
    )

    @field_validator("subsampling")
    @classmethod
    def validate_subsampling(cls, value: Union[int, str]) -> Union[int, str]:
        """
        Validate JPEG subsampling value.
        Accepts either an integer (0, 1, 2)
        or a string ('4:4:4', '4:2:2', '4:2:0').
        Raises ValueError if the value is invalid.
        """
        valid_str = {"4:4:4", "4:2:2", "4:2:0"}
        valid_int = {0, 1, 2}
        if isinstance(value, str):
            if value not in valid_str:
                raise ValueError(f"Invalid subsampling string: {value}")
        elif isinstance(value, int):
            if value not in valid_int:
                raise ValueError(f"Invalid subsampling int: {value}")
        else:
            raise TypeError("Subsampling must be str or int")
        return value


class WebPFormat(OutputFormatBaseModel):
    """WebP output format options compatible with Pillow."""
    name: OutputFormatsEnum = OutputFormatsEnum.WEBP
    quality: int = Field(
        80,
        ge=1,
        le=100,
        description="WebP quality (1-100)"
    )
    lossless: bool = Field(
        False,
        description="Use lossless compression"
    )
    method: Optional[int] = Field(
        None,
        ge=0,
        le=6,
        description="Compression method (0-6)"
    )


class PNGFormat(OutputFormatBaseModel):
    """PNG output format options compatible with Pillow."""
    name: OutputFormatsEnum = OutputFormatsEnum.PNG
    optimize: bool = Field(
        True,
        description="Enable PNG optimization"
    )
    compression_level: int = Field(
        6,
        ge=0,
        le=9,
        description="PNG compression level (0-9)"
    )
    interlace: bool = Field(
        False,
        description="Enable PNG interlacing"
    )


class GIFFormat(OutputFormatBaseModel):
    """GIF output format options compatible with Pillow."""
    name: OutputFormatsEnum = OutputFormatsEnum.GIF
    optimize: bool = Field(
        True,
        description="Enable GIF optimization"
    )


class AVIFFormat(OutputFormatBaseModel):
    """AVIF output format options compatible with Pillow."""
    name: OutputFormatsEnum = OutputFormatsEnum.AVIF
    quality: int = Field(
        80,
        ge=1,
        le=100,
        description="AVIF quality (1-100)"
    )
    lossless: bool = Field(
        False,
        description="Use lossless AVIF compression"
    )


class OutputFormatGroup(BaseModel):
    """Group of formats with optional resize dimensions."""
    fixed_width: Optional[int] = Field(
        None,
        ge=1,
        description="Resize width in pixels"
    )
    fixed_height: Optional[int] = Field(
        None,
        ge=1,
        description="Resize height in pixels"
    )
    fixed_size: Optional[int] = Field(
        None,
        ge=1,
        description="Resize width x height in pixels"
    )
    max_byte_size: Optional[int] = Field(
        None,
        ge=1,
        description="Max byte size for the output image (in bytes)"
    )
    formats: List[
        Union[
            JPEGFormat,
            WebPFormat,
            PNGFormat,
            GIFFormat,
            AVIFFormat
        ]
    ] = Field(
        ...,
        description="List of format-specific export configurations"
    )


class ConfSchema(BaseModel):
    """Main configuration schema for imgtools_m8."""
    source_path: str = Field(
        ...,
        description="Input image folder path",
        pattern=ValidationConstants.FILE_PATH_REGEX.pattern
    )
    include_subdirs: Optional[bool] = Field(
        False,
        description="Include Source Subdirs (default: False)."
    )
    output_path: str = Field(
        ...,
        description="Destination folder for processed images",
        pattern=ValidationConstants.FILE_PATH_REGEX.pattern
    )
    flatten_output: Optional[bool] = Field(
        False,
        description="Output flatten structure (default: False)."
    )
    output_formats: OutputFormatGroup = Field(
        ...,
        description="Output format configurations"
    )
