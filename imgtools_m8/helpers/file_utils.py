"""
file_utils.py

Class-based utility module for file and image file handling.

Provides static methods to work with files including listing,
filtering by extensions, size conversion, and validation.

Author: Eli Serra
Copyright: Copyright 2020, Eli Serra
Date: 2025-06-22
"""
from os.path import getsize, isfile, splitext
from typing import List, Optional

from imgtools_m8.core.constants import VALID_IMAGE_EXTENSIONS


class FileUtils:
    """File and image file utility static methods."""
    @staticmethod
    def get_valid_image_extensions() -> List[str]:
        """
        Returns a sorted list of valid image file extensions.

        Returns:
            List[str]: List of image file extensions including leading dot.
        """
        return sorted(VALID_IMAGE_EXTENSIONS)

    @staticmethod
    def get_file_extension(filepath: str) -> str:
        """
        Extract the lowercase file extension from a file path.

        Args:
            filepath (str): Path to the file.

        Returns:
            str: File extension including leading dot, or empty string.
        """
        _, ext = splitext(filepath)
        return ext.lower()

    @staticmethod
    def is_valid_image_file(
        filepath: str,
        valid_extensions: Optional[List[str]] = None
    ) -> bool:
        """
        Check if file has a valid image extension.

        Args:
            filepath (str): File path to check.
            valid_extensions (Optional[List[str]]): List of valid extensions.
                Defaults to valid image extensions if None.

        Returns:
            bool: True if file extension is valid image, False otherwise.
        """
        if valid_extensions is None:
            valid_extensions = FileUtils.get_valid_image_extensions()
        return FileUtils.get_file_extension(filepath) in valid_extensions

    @staticmethod
    def convert_size(
        size_bytes: int,
        decimal_places: int = 2
    ) -> str:
        """
        Convert size in bytes to a human-readable string.

        Args:
            size_bytes (int): Size in bytes.
            decimal_places (int): Decimal places in formatted string.

        Returns:
            str: Human-readable size string.
        """
        if size_bytes < 0:
            raise ValueError("Size in bytes cannot be negative")

        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        size = float(size_bytes)
        index = 0

        while size >= 1024 and index < len(units) - 1:
            size /= 1024
            index += 1

        return f"{size:.{decimal_places}f} {units[index]}"

    @staticmethod
    def get_file_size_str(
        filepath: str,
        decimal_places: int = 2
    ) -> str:
        """
        Get human-readable file size for a given file path.

        Args:
            filepath (str): Path to the file.
            decimal_places (int): Decimal places for size formatting.

        Returns:
            str: Human-readable file size or error message.
        """
        if not isfile(filepath):
            return "File not found"

        try:
            size_bytes = getsize(filepath)
            return FileUtils.convert_size(size_bytes, decimal_places)
        except OSError:
            return "Unable to determine file size"

    @staticmethod
    def read_file_as_bytes(
        filepath: str
    ) -> Optional[bytes]:
        """
        Read the contents of a file as bytes.

        Args:
            filepath (str): Path to the file.

        Returns:
            Optional[bytes]: File contents or None if cannot read.
        """
        try:
            with open(filepath, "rb") as f:
                return f.read()
        except (OSError, IOError):
            return None

    @staticmethod
    def write_bytes_to_file(
        filepath: str,
        data: bytes
    ) -> bool:
        """
        Write bytes data to a file.

        Args:
            filepath (str): Path to the file.
            data (bytes): Bytes to write.

        Returns:
            bool: True if write succeeded, False otherwise.
        """
        try:
            with open(filepath, "wb") as f:
                f.write(data)
            return True
        except (OSError, IOError):
            return False
