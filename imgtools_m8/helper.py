"""
A helper class for image processing operations.
"""

import math
import os
import pathlib
from typing import Optional, Protocol, Tuple, Union

import platformdirs

from imgtools_m8.core.exceptions import ImgToolsException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


class _HasShape(Protocol):
    """Protocol for objects exposing a .shape attribute (e.g. numpy arrays)."""

    shape: Tuple[int, ...]


class ImageToolsHelper:
    """
    A helper class for image processing operations.
    """

    @staticmethod
    def _validate_combination_args(total: int, numbers: list, label: str) -> None:
        """Raise ImgToolsException if total or numbers are invalid."""
        if not (isinstance(total, int) and total >= 0):
            raise ImgToolsException(
                f"Error: Unable to {label}, 'total' must be a non-negative integer."
            )
        if not (isinstance(numbers, list) and numbers):
            raise ImgToolsException(
                f"Error: Unable to {label}, 'numbers' must be a non-empty list."
            )

    @staticmethod
    def find_best_combination(total: int, numbers: list[int]) -> Optional[list[int]]:
        """
        Find the best combination of numbers to achieve the given total.

        :param total: The target total.
        :type total: int
        :param numbers:
            A list of numbers that can be added to achieve the total.
        :type numbers: list

        :return: The best combination of numbers.
        :rtype: list

        :raises ImgToolsException:
         - If the total is not a non-negative integer
         - if the numbers list is empty or not valid.

        Example:
            >>> ImageToolsHelper.find_best_combination(
                total=10,
                numbers=[2, 3, 5]
            )
            [5, 5]
        """
        ImageToolsHelper._validate_combination_args(
            total, numbers, "find the best combination"
        )
        dp: list[list[int] | None] = [None] * (total + 1)
        dp[0] = []

        for current_total in range(1, total + 1):
            for num in numbers:
                prev_idx = current_total - num
                if prev_idx < 0 or dp[prev_idx] is None:
                    continue
                prev = dp[prev_idx]
                if prev is None:  # pragma: no cover
                    continue
                curr = dp[current_total]
                if curr is None or len(prev) + 1 < len(curr):
                    dp[current_total] = prev + [num]

        return dp[total]

    @staticmethod
    def find_all_combinations(
        total: int, numbers: list[int]
    ) -> Optional[list[list[int]]]:
        """
        Find all combinations of numbers that add up to the given total.

        :param total: The target total.
        :type total: int
        :param numbers:
            A list of numbers that can be added to achieve the total.
        :type numbers: list

        :return: A list of lists containing all possible combinations.
        :rtype: list[list[int]]

        :raises ImgToolsException:
            If the total is not a non-negative integer.
            If the numbers list is empty or not valid.

        Example:
            >>> ImageToolsHelper.find_all_combinations(
                total=5, numbers=[1, 2, 3])
            >>> [[1, 1, 1, 1, 1], [1, 1, 1, 2], [1, 2, 2], [1, 1, 3], [2, 3]]
        """
        ImageToolsHelper._validate_combination_args(total, numbers, "find combinations")
        dp: list[list[list[int]] | None] = [None] * (total + 1)
        dp[0] = [[]]

        for current_total in range(1, total + 1):
            all_combinations: list[list[int]] = []
            for num in numbers:
                prev_idx = current_total - num
                if prev_idx < 0 or dp[prev_idx] is None:
                    continue
                prev = dp[prev_idx]
                if prev is None:  # pragma: no cover
                    continue
                for combination in prev:
                    all_combinations.append(combination + [num])
            dp[current_total] = all_combinations

        return dp[total]

    @staticmethod
    def is_image_size(size: tuple) -> bool:
        """
        Check if the given size tuple represents valid image dimensions.

        :param size: The size tuple (height, width) to be checked.
        :type size: tuple[int, int]

        :return: True if the size is a valid image size, False otherwise.
        :rtype: bool

        Example:
            >>> valid_size = (480, 640)
            >>> invalid_size = (0, 800)
            >>> ImageToolsHelper.is_image_size(valid_size)
            True
            >>> ImageToolsHelper.is_image_size(invalid_size)
            False
        """
        return (
            isinstance(size, tuple)
            and len(size) >= 2
            and isinstance(size[0], int)
            and size[0] >= 1
            and isinstance(size[1], int)
            and size[1] >= 1
        )

    @staticmethod
    def get_image_size(image: Optional[_HasShape]) -> Optional[tuple]:
        """
        Get the dimensions (height and width) of an image
        represented as a NumPy array.

        :param image: The image as a NumPy array.
        :type image: numpy.ndarray or None

        :return:
            The image dimensions as a tuple (height, width),
            or None if image is None.
        :rtype: tuple[int, int] or None

        Example:
            >>> import numpy as np
            >>> image_data = np.zeros((480, 640, 3), dtype=np.uint8)
            >>> ImageToolsHelper.get_image_size(image_data)
            (480, 640)
            >>> ImageToolsHelper.get_image_size(None)
        None
        """
        if image is not None:
            return image.shape[:2]
        return None

    @staticmethod
    def get_default_models_path(segment: str = "opencv") -> str:
        """
        Resolve the default directory holding super-resolution models.

        Resolution order (cv2-independent):

        1. ``IMGTOOLS_M8_MODELS_DIR`` environment override → ``{env}/{segment}``.
        2. The platform user cache dir, when it already holds the models.
        3. The co-located ``assets/models/{segment}`` source tree
           (editable / source installs).
        4. Otherwise the platform user cache dir (pure wheel installs).

        :param segment: Backend sub-directory (e.g. ``"opencv"``).
        :type segment: str

        :return: Absolute path to the resolved models directory.
        :rtype: str

        Example:
            >>> ImageToolsHelper.get_default_models_path()
            '/home/user/.cache/imgtools_m8/models/opencv'
        """
        env_dir = os.environ.get("IMGTOOLS_M8_MODELS_DIR")
        if env_dir:
            return os.path.join(env_dir, segment)

        cache_dir = os.path.join(
            platformdirs.user_cache_dir("imgtools_m8", appauthor=False),
            "models",
            segment,
        )
        if os.path.isdir(cache_dir):
            return cache_dir

        source_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "models", segment
        )
        if os.path.isdir(source_dir):
            return source_dir

        return cache_dir

    @staticmethod
    def get_images_list(path: str) -> Optional[list]:
        """
        Get a list of image files from the specified path.

        :param path: The path to the directory containing image files.
        :type path: str

        :return: A list of image file paths.
        :rtype: list[str]

        Example:
            >>> ImageToolsHelper.get_images_list('/path/to/images')
            ['/path/to/images/image1.jpg', '/path/to/images/image2.png', ...]
        """
        return ImageToolsHelper.get_files_list(
            path, ext=ImageToolsHelper.get_valid_images_ext()
        )

    @staticmethod
    def _ext_matches(file_name: str, ext: Optional[Union[str, list]]) -> bool:
        """Return True if file_name matches the given extension filter."""
        if ext is None:
            return True
        file_ext = ImageToolsHelper.get_extension(file_name)
        if isinstance(ext, list) and ext:
            return file_ext in ext
        if isinstance(ext, str) and ext:
            return file_ext == ext
        return False  # pragma: no cover

    @staticmethod
    def _name_matches(file_name: str, content_name: Optional[str]) -> bool:
        """Return True if file_name contains content_name (or content_name is None)."""
        if content_name is None:
            return True
        return (
            isinstance(content_name, str)
            and bool(content_name)
            and content_name in file_name
        )

    @staticmethod
    def get_files_list(
        path: str,
        ext: Optional[Union[str, list]] = None,
        content_name: Optional[str] = None,
    ) -> Optional[list]:
        """
        Get a list of files from the specified path,
        with optional filtering by extensions and content name.

        :param path: The path to the directory to list files from.
        :type path: str
        :param ext: Optional filter for file extensions.
        :type ext: str, list, None
        :param content_name:
            Optional filter for file names containing specific content.
        :type content_name: str, None

        :return:
            A list of file names matching the filters,
            or None if path is not a directory.
        :rtype: list[str] or None

        Example:
            >>> ImageToolsHelper.get_files_list(
                '/path/to/files', ext=['jpg', 'png'],
                content_name='image'
            )
            ['image1.jpg', 'image2.png', ...]
        """
        if not (isinstance(path, str) and path and os.path.isdir(path)):
            return None
        return [
            f
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
            and ImageToolsHelper._ext_matches(f, ext)
            and ImageToolsHelper._name_matches(f, content_name)
        ]

    @staticmethod
    def get_valid_images_ext() -> list:
        """
        Get a list of valid image file extensions.

        :return: A list of valid image file extensions.
        :rtype: list[str]

        Example:
            >>> ImageToolsHelper.get_valid_images_ext()
            ['.bmp', '.dib', '.jpg', '.jpeg', '.jpe', '.jp2', '.png', ...]
        """
        return [
            ".bmp",
            ".dib",
            ".jpg",
            ".jpeg",
            ".jpe",
            ".jp2",
            ".png",
            ".webp",
            ".avif",
            ".pbm",
            ".pgm",
            ".ppm",
            ".pxm",
            ".pnm",
            ".pfm",
            ".sr",
            ".ras",
            ".tiff",
            ".tif",
            ".exr",
            ".hdr",
            ".pic",
        ]

    @staticmethod
    def get_valid_jpg_ext() -> list:
        """
        Get a list of valid file extensions for JPEG image files.

        :return: A list of valid extensions for JPEG image files.
        :rtype: list[str]

        Example:
            >>> ImageToolsHelper.get_valid_jpg_ext()
            ['.jpg', '.jpeg', '.jpe', '.jp2']
        """
        return [".jpg", ".jpeg", ".jpe", ".jp2"]

    @staticmethod
    def is_valid_image_ext(ext: str) -> bool:
        """
        Check if a given file extension is valid for an image.

        :param ext: The file extension to check.
        :type ext: str

        :return: True if the extension is valid for an image, False otherwise.
        :rtype: bool

        Example:
            >>> ImageToolsHelper.is_valid_image_ext('.png')
                True
        """
        result = False
        if isinstance(ext, str) and ext:
            ext = ext.lower()
            result = ext in ImageToolsHelper.get_valid_images_ext()
        return result

    @staticmethod
    def is_valid_jpg_ext(ext: str):
        """
        Check if a given file extension is valid for a JPEG image.

        :param ext: The file extension to check.
        :type ext: str

        :return:
            True if the extension is valid for a JPEG image,
            False otherwise.
        :rtype: bool

        Example:
            >>> ImageToolsHelper.is_valid_jpg_ext('.jpg')
            True
        """
        ext = ext.lower()
        return ext in ImageToolsHelper.get_valid_jpg_ext()

    @staticmethod
    def cut_file_name(file_name: str, ext_len: int = 1) -> tuple:
        """
        Split a file name into the base name and extension.

        :param file_name: The file name to be split.
        :type file_name: str
        :param ext_len: The length of the extension. Default is 1.
        :type ext_len: int

        :return:
            A tuple containing the base name and extension,
            or (None, None) if invalid input.
        :rtype: tuple

        Example:
            >>> ImageToolsHelper.cut_file_name("image.jpg")
            ('image', '.jpg')
        """
        name = None
        ext = ImageToolsHelper.get_extension(file_name, ext_len)
        if isinstance(file_name, str) and file_name and isinstance(ext, str):
            name = file_name.replace(ext, "")
        return name, ext

    @staticmethod
    def get_extension(path: str, ext_len: int = 1) -> str:
        """
        Get the file extension from a file path.

        :param path: The file path.
        :type path: str
        :param ext_len:
            The desired length of the extension to retrieve.
            Default is 1.
        :type ext_len: int

        :return: The file extension, or an empty string if invalid input.
        :rtype: str

        Example:
            >>> ImageToolsHelper.get_extension("image.jpg")
            '.jpg'
        """
        if not (isinstance(path, str) and path):
            return ""
        ext_len = ext_len if isinstance(ext_len, int) else 1
        if ext_len == 1:
            ext = pathlib.Path(path).suffix
        elif ext_len == 2:
            ext = "".join(pathlib.Path(path).suffixes[-2:])
        elif ext_len == 3:
            ext = "".join(pathlib.Path(path).suffixes[-3:])
        else:
            ext = "".join(pathlib.Path(path).suffixes)
        return ext.lower()

    @staticmethod
    def convert_size(size_bytes):
        """
        Convert bytes to a more human-readable size unit.

        :param size_bytes: The size in bytes.
        :type size_bytes: int

        :return: The formatted size string with unit.
        :rtype: str

        Example:
            >>> ImageToolsHelper.convert_size(2048)
            '2.0 KB'
        """
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    @staticmethod
    def get_string_file_size(source_path: str) -> str:
        """
        Get the formatted file size from a file path.

        :param source_path: The path to the file.
        :type source_path: str

        :return:
            The formatted file size string with unit,
            or an empty string if the path is not a file.
        :rtype: str

        Example:
            >>> ImageToolsHelper.get_string_file_size("image.jpg")
            '2.0 KB'
        """
        result = ""
        if os.path.isfile(source_path):
            result = ImageToolsHelper.convert_size(os.path.getsize(source_path))
        return result
