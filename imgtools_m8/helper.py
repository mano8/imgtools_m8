"""
A helper class for image processing operations.
"""
import os
import pathlib
import math
from numpy import ndarray
from ve_utils.utils import UType as Ut
from imgtools_m8.exceptions import ImgToolsException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class ImageToolsHelper:
    """
        A helper class for image processing operations.
    """

    @staticmethod
    def find_best_combination(total: int,
                              numbers: list
                              ) -> list:
        """
        Find the best combination of numbers to achieve the given total.

        :param total: The target total.
        :type total: int
        :param numbers: A list of numbers that can be added to achieve the total.
        :type numbers: list

        :return: The best combination of numbers.
        :rtype: list

        :raises ImgToolsException:
         - If the total is not a non-negative integer
         - if the numbers list is empty or not valid.

        Example:
            >>> ImageToolsHelper.find_best_combination(total=10, numbers=[2, 3, 5])
            [5, 5]
        """
        if not Ut.is_int(total, mini=0):
            raise ImgToolsException(
                "Error: Unable to find the best combination, 'total' must be a non-negative integer."
            )

        if not Ut.is_list(numbers, not_null=True):
            raise ImgToolsException(
                "Error: Unable to find the best combination, 'numbers' must be a non-empty list."
            )
        dp = [None] * (total + 1)
        dp[0] = []

        for current_total in range(1, total + 1):
            for num in numbers:
                if current_total - num >= 0 and dp[current_total - num] is not None:
                    if dp[current_total] is None or len(dp[current_total - num]) + 1 < len(dp[current_total]):
                        dp[current_total] = dp[current_total - num] + [num]

        return dp[total]

    @staticmethod
    def find_all_combinations(total: int, numbers: list) -> list:
        """
        Find all combinations of numbers that add up to the given total.

        :param total: The target total.
        :type total: int
        :param numbers: A list of numbers that can be added to achieve the total.
        :type numbers: list

        :return: A list of lists containing all possible combinations.
        :rtype: list[list[int]]

        :raises ImgToolsException:
            If the total is not a non-negative integer.
            If the numbers list is empty or not valid.

        Example:
            >>> ImageToolsHelper.find_all_combinations(total=5, numbers=[1, 2, 3])
            >>> [[1, 1, 1, 1, 1], [1, 1, 1, 2], [1, 2, 2], [1, 1, 3], [2, 3]]
        """
        if not Ut.is_int(total, mini=0):
            raise ImgToolsException(
                "Error: Unable to find combinations, 'total' must be a non-negative integer."
            )

        if not Ut.is_list(numbers, not_null=True):
            raise ImgToolsException(
                "Error: Unable to find combinations, 'numbers' must be a non-empty list."
            )
        dp = [None] * (total + 1)
        dp[0] = [[]]

        for current_total in range(1, total + 1):
            all_combinations = []
            for num in numbers:
                if current_total - num >= 0 and dp[current_total - num] is not None:
                    for combination in dp[current_total - num]:
                        new_combination = combination + [num]
                        all_combinations.append(new_combination)

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
        return Ut.is_tuple(size) \
            and Ut.is_int(size[0], mini=1) \
            and Ut.is_int(size[1], mini=1)

    @staticmethod
    def get_image_size(image: ndarray) -> tuple or None:
        """
        Get the dimensions (height and width) of an image represented as a NumPy array.

        :param image: The image as a NumPy array.
        :type image: numpy.ndarray

        :return: The image dimensions as a tuple (height, width), or None if image is None.
        :rtype: tuple[int, int] or None

        Example:
            >>> import numpy as np
            >>> image_data = np.zeros((480, 640, 3), dtype=np.uint8)
            >>> ImageToolsHelper.get_image_size(image_data)
            (480, 640)
            >>> ImageToolsHelper.get_image_size(None)
        None
        """
        size = None
        if image is not None:
            size = image.shape[:2]
        return size

    @staticmethod
    def get_package_models_path() -> str or None:
        """
        Get the path to the package models' directory.

        :return: The path to the package models' directory, or None if not found.
        :rtype: str or None

        Example:
            >>> ImageToolsHelper.get_package_models_path()
        '/path/to/package/models'
        """
        return os.path.join(os.path.dirname(__file__), 'models')

    @staticmethod
    def get_images_list(path: str) -> list:
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
        return ImageToolsHelper.get_files_list(path, ext=ImageToolsHelper.get_valid_images_ext())

    @staticmethod
    def get_files_list(path: str,
                       ext: str or list or None = None,
                       content_name: str or None = None
                       ) -> list or None:
        """
        Get a list of files from the specified path, with optional filtering by extensions and content name.

        :param path: The path to the directory to list files from.
        :type path: str
        :param ext: Optional filter for file extensions.
        :type ext: str, list, None
        :param content_name: Optional filter for file names containing specific content.
        :type content_name: str, None

        :return: A list of file names matching the filters, or None if path is not a directory.
        :rtype: list[str] or None

        Example:
            >>> ImageToolsHelper.get_files_list('/path/to/files', ext=['jpg', 'png'], content_name='image')
            ['image1.jpg', 'image2.png', ...]
        """
        result = None
        if Ut.is_str(path, not_null=True) \
                and os.path.isdir(path):
            result = [
                f
                for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f))
                and (ext is None
                     or (Ut.is_list(ext, not_null=True) and ImageToolsHelper.get_extension(f) in ext)
                     or (Ut.is_str(ext, not_null=True) and ImageToolsHelper.get_extension(f) == ext)
                     )
                and (content_name is None
                     or (Ut.is_str(content_name, not_null=True) and content_name in f)
                     )
            ]
        return result

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
            '.bmp', '.dib',
            '.jpg', '.jpeg', '.jpe',
            '.jp2', '.png', '.webp',
            '.avif', '.pbm', '.pgm',
            '.ppm', '.pxm', '.pnm',
            '.pfm', '.sr', '.ras',
            '.tiff', '.tif', '.exr',
            '.hdr', '.pic'
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
        return [
            '.jpg', '.jpeg', '.jpe', '.jp2'
        ]

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
        if Ut.is_str(ext, not_null=True):
            ext = ext.lower()
            result = ext in ImageToolsHelper.get_valid_images_ext()
        return result

    @staticmethod
    def is_valid_jpg_ext(ext: str):
        """
        Check if a given file extension is valid for a JPEG image.

        :param ext: The file extension to check.
        :type ext: str

        :return: True if the extension is valid for a JPEG image, False otherwise.
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

        :return: A tuple containing the base name and extension, or (None, None) if invalid input.
        :rtype: tuple

        Example:
            >>> ImageToolsHelper.cut_file_name("image.jpg")
            ('image', '.jpg')
        """
        name = None
        ext = ImageToolsHelper.get_extension(file_name, ext_len)
        if Ut.is_str(file_name, not_null=True) \
                and Ut.is_str(ext):
            name = file_name.replace(ext, '')
        return name, ext

    @staticmethod
    def get_extension(path: str, ext_len: int = 1) -> str:
        """
        Get the file extension from a file path.

        :param path: The file path.
        :type path: str
        :param ext_len: The desired length of the extension to retrieve. Default is 1.
        :type ext_len: int

        :return: The file extension, or an empty string if invalid input.
        :rtype: str

        Example:
            >>> ImageToolsHelper.get_extension("image.jpg")
            '.jpg'
        """
        ext = None
        if Ut.is_str(path, not_null=True):
            ext_len = Ut.get_int(ext_len, default=1)
            if ext_len == 1:
                ext = pathlib.Path(path).suffix
            elif ext_len == 2:
                ext_list = pathlib.Path(path).suffixes[-2:]
                ext = "".join(ext_list)
            elif ext_len == 3:
                ext_list = pathlib.Path(path).suffixes[-3:]
                ext = "".join(ext_list)
            else:
                ext = "".join(pathlib.Path(path).suffixes)
            ext = ext.lower()
        return ext

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
        return "%s %s" % (s, size_name[i])

    @staticmethod
    def get_string_file_size(source_path: str) -> str:
        """
        Get the formatted file size from a file path.

        :param source_path: The path to the file.
        :type source_path: str

        :return: The formatted file size string with unit, or an empty string if the path is not a file.
        :rtype: str

        Example:
            >>> ImageToolsHelper.get_string_file_size("image.jpg")
            '2.0 KB'
        """
        result = ""
        if os.path.isfile(source_path):
            result = ImageToolsHelper.convert_size(
                os.path.getsize(source_path)
            )
        return result
