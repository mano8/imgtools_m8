"""
image_utils.py

Class-based utility module for common image processing tasks.

Provides static methods for image validation, metadata extraction,
format conversion, resizing, and more.

Author: Your Name
Date: 2025-06-22
"""

import logging
from typing import Optional, Tuple, Union

from PIL import Image, UnidentifiedImageError

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"

logger = logging.getLogger("imgTools_m8")


class ImageUtils:
    """Static methods for image file processing and validation."""

    @staticmethod
    def is_valid_image(filepath: str) -> bool:
        """
        Verify if a file is a valid image by attempting to open it.

        Args:
            filepath (str): Path to the image file.

        Returns:
            bool: True if file is a valid image, False otherwise.
        """
        try:
            with Image.open(filepath) as img:
                img.verify()
            return True
        except (IOError, UnidentifiedImageError):
            return False

    @staticmethod
    def get_image_size(filepath: str) -> Optional[Tuple[int, int]]:
        """
        Get the dimensions (width, height) of an image.

        Args:
            filepath (str): Path to the image file.

        Returns:
            Optional[Tuple[int, int]]: Width and height in pixels,
                or None if file is invalid or inaccessible.
        """
        try:
            with Image.open(filepath) as img:
                return img.size
        except (IOError, UnidentifiedImageError):
            return None

    @staticmethod
    def get_image_format(filepath: str) -> Optional[str]:
        """
        Retrieve the image format of a given image file.

        Args:
            filepath (str): Path to image file.

        Returns:
            Optional[str]:
                Format name (e.g., 'JPEG', 'PNG') or None if invalid.
        """
        try:
            with Image.open(filepath) as img:
                return img.format
        except (IOError, UnidentifiedImageError):
            return None

    @staticmethod
    def get_image_format_type(
        image_size: Tuple[int, int]
    ) -> Optional[str]:
        """
        Determine the image format type based on its dimensions.

        Args:
            image_size (Tuple[int]): Tuple containing width and height.

        Returns:
            Optional[str]: Format type ('portrait', 'landscape', 'square')
                or None if size is invalid.
        """
        result = None
        if ImageUtils.is_valid_size(image_size) is False:
            return None

        width, height = image_size

        if width == height:
            result = "square"
        elif width > height:
            result = "landscape"
        else:
            result = "portrait"
        return result

    @staticmethod
    def get_image_info(
        filepath: str,
        image_size: bool = True,
        image_format: bool = True,
        is_valid: bool = True
    ) -> Optional[Tuple[int, int]]:
        """
        Retrieve various metadata about an image file.
        Args:
            filepath (str): Path to the image file.
            image_size (bool): Whether to include image dimensions.
                Defaults to True.
            image_format (bool): Whether to include image format.
                Defaults to True.
            is_valid (bool): Whether to check if the image is valid.
                Defaults to True.
        Returns:
            Optional[dict]: Dictionary with image metadata if requested,
                or None if no metadata requested or file is invalid.
        """
        result = None
        try:
            if image_size is True\
                    or is_valid is True:
                result = {}
                with Image.open(filepath) as img:
                    if image_size is True:
                        result['image_size'] = img.size
                    if image_format is True:
                        result['image_format'] = img.format
                    if is_valid is True:
                        result['is_valid'] = img.verify() is None
        except (IOError, UnidentifiedImageError):
            if image_size is True\
                    or is_valid is True:
                result = {}
                if image_size is True:
                    result['image_size'] = None
                if image_format is True:
                    result['image_format'] = None
                if is_valid is True:
                    result['is_valid'] = False
            else:
                result = None
        return result

    @staticmethod
    def is_valid_dimension(
        dim: Union[int, float]
    ) -> bool:
        """
        Check if the provided size is a valid tuple of two positive numbers.

        Args:
            size (Tuple[float, float]): Size to validate.

        Returns:
            bool: True if size is valid, False otherwise.
        """
        return isinstance(dim, (int, float)) and dim > 0

    @staticmethod
    def is_valid_size(
        size: Tuple[float, float]
    ) -> bool:
        """
        Check if the provided size is a valid tuple of two positive numbers.

        Args:
            size (Tuple[float, float]): Size to validate.

        Returns:
            bool: True if size is valid, False otherwise.
        """
        return isinstance(size, tuple) and len(size) == 2\
            and all(ImageUtils.is_valid_dimension(dim) for dim in size)

    @staticmethod
    def get_new_scale(
        size: Tuple[float, float],
        fixed_width: Optional[float],
        fixed_height: Optional[float],
    ) -> Tuple[float, float]:
        """
        Calculate new image dimensions preserving aspect ratio,
        allowing upscaling.

        Args:
            size (Tuple[float, float]): Original image size (width, height).
            fixed_width (Optional[float]): Max or fixed width to scale to.
            fixed_height (Optional[float]): Max or fixed height to scale to.

        Returns:
            Tuple[float, float]: New scaled (width, height) dimensions.

        Raises:
            ValueError: If the original size or any fixed dimension is invalid,
                        or if no fixed dimension is provided.
        """
        if not ImageUtils.is_valid_size(size):
            logger.error("Invalid original image size: %s", size)
            raise ValueError("Invalid original image size provided.")

        def validate_dimension(value: Optional[float], name: str):
            if value is not None and not ImageUtils.is_valid_dimension(value):
                logger.error("Invalid %s: %s", name, value)
                raise ValueError(f"Invalid {name} dimension.")

        validate_dimension(fixed_width, "fixed_width")
        validate_dimension(fixed_height, "fixed_height")

        original_width, original_height = size
        aspect_ratio = original_width / original_height

        if fixed_width is not None and fixed_height is not None:
            # Scale image to fit within bounding box
            # defined by fixed_width x fixed_height
            width_scale = fixed_width / original_width
            height_scale = fixed_height / original_height
            scale = min(width_scale, height_scale)

            new_width = round(original_width * scale, 3)
            new_height = round(original_height * scale, 3)
            return new_width, new_height

        elif fixed_width is not None:
            new_height = round(fixed_width / aspect_ratio, 3)
            return fixed_width, new_height

        elif fixed_height is not None:
            new_width = round(fixed_height * aspect_ratio, 3)
            return new_width, fixed_height

        logger.error("No fixed dimensions provided for scaling.")
        raise ValueError(
            "At least one of fixed_width or fixed_height must be provided.")

    @staticmethod
    def get_center_crop_box(
        size: Tuple[float, float],
        target_width: float,
        target_height: float
    ) -> Tuple[int, int, int, int]:
        """
        Calculate crop box (left, upper, right, lower) to crop image centered
        to the target width and height.

        Args:
            size (Tuple[float, float]): Original image size (width, height).
            target_width (float): Desired width after crop.
            target_height (float): Desired height after crop.

        Returns:
            Tuple[int, int, int, int]: Crop box (left, upper, right, lower).

        Raises:
            ValueError: If target size is invalid or larger than original.
        """
        if not ImageUtils.is_valid_size(size):
            logger.error("Invalid original image size: %s", size)
            raise ValueError("Invalid image size provided.")

        if not ImageUtils.is_valid_size((target_width, target_height)):
            logger.error(
                "Invalid crop target size: %s x %s",
                target_width,
                target_height
            )
            raise ValueError("Invalid crop target size provided.")

        orig_width, orig_height = size

        if target_width > orig_width or target_height > orig_height:
            logger.error(
                "Crop target size exceeds original image size: "
                "original (%s x %s), target (%s x %s)",
                orig_width, orig_height, target_width, target_height
            )
            raise ValueError("Crop target size exceeds original image size.")

        left = int((orig_width - target_width) / 2)
        upper = int((orig_height - target_height) / 2)
        right = left + int(target_width)
        lower = upper + int(target_height)

        return left, upper, right, lower

    @staticmethod
    def resize_image(
        filepath: str,
        output_path: str,
        max_width: int,
        max_height: int,
        maintain_aspect_ratio: bool = True,
    ) -> bool:
        """
        Resize an image to fit within max dimensions and save it.

        Args:
            filepath (str): Path to input image.
            output_path (str): Path where resized image will be saved.
            max_width (int): Maximum width in pixels.
            max_height (int): Maximum height in pixels.
            maintain_aspect_ratio (bool): Whether to keep aspect ratio.
                Defaults to True.

        Returns:
            bool: True if resize and save succeeded, False otherwise.
        """
        try:
            with Image.open(filepath) as img:
                if maintain_aspect_ratio:
                    img.thumbnail((max_width, max_height))
                else:
                    img = img.resize((max_width, max_height))

                img.save(output_path)
            return True
        except (IOError, UnidentifiedImageError):
            return False

    @staticmethod
    def get_format_kwargs(
        output_format: str,
        format_args,
    ) -> Optional[dict]:
        """Get format-specific kwargs for PIL Image.save (excludes 'ext')."""
        if isinstance(output_format, str) and format_args is not None:
            return format_args.model_dump(exclude={'ext'})
        return None

    @staticmethod
    def convert_image_format(
        filepath: str,
        output_path: str,
        output_format: str,
        format_args,
    ) -> bool:
        """
        Convert an image to a different format and save it.

        Args:
            filepath (str): Path to input image.
            output_path (str): Path where converted image will be saved.
            output_format (str):
                Format to convert to (e.g., "JPEG", "PNG", "WEBP", "GIF").
            format_args: Format-specific arguments (Pydantic model).

        Returns:
            bool: True if conversion succeeded, False otherwise.
        """
        if not isinstance(output_format, str):
            return False
        fmt = output_format.upper()
        if fmt not in {"JPEG", "PNG", "WEBP", "GIF"}:
            return False
        try:
            with Image.open(filepath) as img:
                save_kwargs = ImageUtils.get_format_kwargs(
                    output_format=output_format,
                    format_args=format_args
                )
                if fmt in {"JPEG", "JPG"}:
                    img = img.convert("RGB")
                elif fmt in {"PNG", "WEBP"} and img.mode not in {"RGBA", "LA"}:
                    img = img.convert("RGBA")
                img.save(
                    output_path,
                    format=output_format.upper(),
                    **save_kwargs
                )
            return True
        except (IOError, UnidentifiedImageError, ValueError):
            return False
