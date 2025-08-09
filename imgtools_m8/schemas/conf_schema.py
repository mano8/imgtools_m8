"""
Schemas for Pillow-compatible output format optimizations in imgtools_m8.
"""

from typing import List, Literal, Optional, Union
from typing_extensions import Annotated

from pydantic import BaseModel, Field, model_validator

from imgtools_m8.core.constants import OutputFormatsEnum

JPEG_SUBSAMPLING_OPTIONS = [
    '4:4:4', '4:2:2', '4:2:0'
]


class JpegFormat(BaseModel):
    """JPEG output format options."""
    ext: Literal[OutputFormatsEnum.JPEG] = Field(
        OutputFormatsEnum.JPEG.value, description='JPEG format.'
    )
    quality: Optional[int] = Field(
        None, ge=1, le=100,
        description='JPEG quality (1-100).'
    )
    optimize: Optional[bool] = Field(
        False, description='Enable Huffman table optimization.'
    )
    progressive: Optional[bool] = Field(
        False, description='Use progressive JPEG encoding.'
    )
    subsampling: Optional[
        Union[int, Literal['4:4:4', '4:2:2', '4:2:0']]
    ] = Field(
        None,
        description='Chroma subsampling: integer or string format.'
    )

    @staticmethod
    def is_subsampling_valid(
        subsampling: Union[int, Literal['4:4:4', '4:2:2', '4:2:0']]
    ) -> bool:
        """Check if the subsampling value is valid."""
        if isinstance(subsampling, int):
            return 0 <= subsampling < len(JPEG_SUBSAMPLING_OPTIONS)
        return subsampling in JPEG_SUBSAMPLING_OPTIONS

    @model_validator(mode='after')
    def check_constraints(self) -> 'OutputOptions':
        """Ensure valid combination of size constraints."""
        nb_sampling = len(JPEG_SUBSAMPLING_OPTIONS)
        if not self.is_subsampling_valid(self.subsampling)\
                and self.subsampling is not None:
            raise ValueError(
                'Invalid subsampling option.'
                ' Valid options are:'
                f' {JPEG_SUBSAMPLING_OPTIONS} or '
                f'integers from 0 to {nb_sampling - 1}.'
            )

        return self


class WebpFormat(BaseModel):
    """WebP output format options."""
    ext: Literal[OutputFormatsEnum.WEBP] = Field(
        OutputFormatsEnum.WEBP.value, description='WEBP format.'
    )
    quality: Optional[int] = Field(
        None, ge=1, le=100, description='WebP quality (1-100).'
    )
    lossless: Optional[bool] = Field(
        False, description='Enable lossless compression.'
    )
    method: Optional[int] = Field(
        None, ge=0, le=6, description='Compression method (0-6).'
    )


class PngFormat(BaseModel):
    """PNG output format options."""
    ext: Literal[OutputFormatsEnum.PNG] = Field(
        OutputFormatsEnum.PNG.value, description='PNG format.'
    )
    optimize: Optional[bool] = Field(
        False, description='Enable PNG optimization.'
    )
    compression_level: Optional[int] = Field(
        None, ge=0, le=9, description='Compression level (0-9).'
    )
    interlace: Optional[bool] = Field(
        False, description='Enable PNG interlacing.'
    )


class GifFormat(BaseModel):
    """GIF output format options."""
    ext: Literal[OutputFormatsEnum.GIF] = Field(
        OutputFormatsEnum.GIF.value, description='GIF format.'
    )
    optimize: Optional[bool] = Field(
        False, description='Enable GIF optimization.'
    )


class AvifFormat(BaseModel):
    """AVIF output format options."""
    ext: Literal[OutputFormatsEnum.AVIF] = Field(
        OutputFormatsEnum.AVIF.value, description='AVIF format.'
    )
    quality: Optional[int] = Field(
        None, ge=1, le=100, description='AVIF quality (1-100).'
    )
    lossless: Optional[bool] = Field(
        False, description='Enable lossless compression.'
    )


FormatsList = (
    JpegFormat,
    WebpFormat,
    PngFormat,
    GifFormat,
    AvifFormat,
)


FormatConfig = Annotated[
    Union[
        JpegFormat,
        WebpFormat,
        PngFormat,
        GifFormat,
        AvifFormat,
    ],
    Field(discriminator='ext')
]


class OutputSize(BaseModel):
    """
    Resize or convert output image formats and options.

    At least one of the following must be set:
    fixed_width, fixed_height, fixed_size, or formats.
    """

    fixed_width: Optional[int] = Field(
        None, gt=0, description='Resize to a fixed width (px).'
    )
    fixed_height: Optional[int] = Field(
        None, gt=0, description='Resize to a fixed height (px).'
    )
    fixed_size: Optional[int] = Field(
        None, gt=0, description='Resize preserving aspect ratio, '
        'largest dimension constrained.'
    )
    fixed_upscale: Optional[int] = Field(
        None,
        ge=2,
        le=10,
        description='Resize preserving aspect ratio, '
        'largest dimension constrained, with upscaling factor.'
    )
    fixed_downscale: Optional[int] = Field(
        None,
        ge=2,
        le=10,
        description='Resize preserving aspect ratio, '
        'largest dimension constrained, with downscaling factor.'
    )

    @model_validator(mode='after')
    def check_constraints(self) -> 'OutputSize':
        """Ensure valid combination of size constraints."""
        if self.fixed_size is not None\
                and (self.fixed_width or self.fixed_height):
            raise ValueError(
                'fixed_size cannot be combined with fixed_width or '
                'fixed_height.'
            )
        if self.fixed_upscale is not None\
                and (self.fixed_width or self.fixed_height):
            raise ValueError(
                'fixed_upscale cannot be combined with fixed_width or '
                'fixed_height.'
            )
        if self.fixed_downscale is not None\
                and (self.fixed_width or self.fixed_height):
            raise ValueError(
                'fixed_downscale cannot be combined with fixed_width or '
                'fixed_height.'
            )
        return self


class OutputOptions(BaseModel):
    """Resize or convert output image formats and options.

    At least one of the following must be set:
    fixed_width, fixed_height, fixed_size, or formats.
    """

    image_size: Optional[OutputSize] = Field(
        None, description='Image size constraints for resizing.'
    )
    allow_upscale: Optional[bool] = Field(
        False, description='Allow upscaling when image is too small.'
    )
    max_byte_size: Optional[int] = Field(
        None, gt=0, description='Target max byte size per image.'
    )
    formats: Optional[List[FormatConfig]] = Field(
        None, description='List of format configs (jpeg, png, etc.).'
    )

    @model_validator(mode='after')
    def check_constraints(self) -> 'OutputOptions':
        """Ensure valid combination of size constraints and formats."""
        if (
            self.image_size is not None
            and self.image_size.fixed_upscale is not None
        ):
            self.allow_upscale = True

        if not (
            self.max_byte_size is not None
            or self.image_size is not None
            or self.formats is not None
        ):
            raise ValueError(
                'At least one of image_size, max_byte_size, '
                'or formats must be set.'
            )
        return self


class GlobalOutputOptions(BaseModel):
    """Resize or convert output image formats and options.

    At least one of the following must be set:
    fixed_width, fixed_height, fixed_size, or formats.
    """

    max_byte_size: Optional[int] = Field(
        None, gt=0, description='Target max byte size per image.'
    )
    formats: Optional[List[FormatConfig]] = Field(
        None, description='List of format configs (jpeg, png, etc.).'
    )

    @model_validator(mode='after')
    def check_constraints(self) -> 'OutputOptions':
        """Ensure valid combination of size constraints and formats."""

        if not (
            self.max_byte_size is not None
            or self.formats is not None
        ):
            raise ValueError(
                'At least one of image_size, max_byte_size, '
                'or formats must be set.'
            )
        return self


class ImageProcessingSchema(BaseModel):
    """Top-level image processing schema.

    Defines input/output paths and optional output format config.
    """

    source_path: str = Field(
        ..., description='Path to image file or directory.'
    )
    include_subdirs: Optional[bool] = Field(
        False,
        description='Process subdirectories (up to depth 4).'
    )
    output_path: str = Field(
        ..., description='Output directory for saved images.'
    )
    flatten_output: Optional[bool] = Field(
        False,
        description='Flatten all outputs into one dir if using subdirs.'
    )
    output_options: Optional[List[OutputOptions]] = Field(
        None, description='Image resizing and conversion options.'
    )
    global_options: Optional[GlobalOutputOptions] = Field(
        None, description='Image global output options.'
    )

    @model_validator(mode='after')
    def check_constraints(self) -> 'OutputOptions':
        """Ensure valid constraints."""
        if self.flatten_output is True:
            self.include_subdirs = True

        if (
            self.output_options is None
            and self.global_options is None
            and self.flatten_output is False
        ):
            raise ValueError(
                'At least one of output_options, flatten_output, '
                'or global_options must be set.'
            )
        return self
