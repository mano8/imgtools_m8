"""
ImageToolsHelper unittest class.

Use pytest package.
"""

from os.path import join

import pytest

from imgtools_m8.helpers.image_utils import ImageUtils

from ..helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


class TestImageUtils:
    """ImageUtils unittest class."""

    @staticmethod
    def test_is_valid_image():
        """Test is_valid_image method"""
        source_path = HelperTest.get_source_path()
        assert ImageUtils.is_valid_image(join(source_path, "cat1", "mar.jpg"))
        assert not ImageUtils.is_valid_image(join(source_path, "cat1", "mar.exe"))
        assert not ImageUtils.is_valid_image(join(source_path, "cat1", "bad_file.txt"))

    @staticmethod
    def test_get_image_size():
        """Test get_image_size method"""
        source_path = HelperTest.get_source_path()
        size = ImageUtils.get_image_size(join(source_path, "cat1", "mar.jpg"))
        assert size == (276, 397)
        size = ImageUtils.get_image_size(join(source_path, "cat1", "mar.exe"))
        assert size is None

    @staticmethod
    def test_get_image_format():
        """Test get_image_format method"""
        source_path = HelperTest.get_source_path()
        image_format = ImageUtils.get_image_format(join(source_path, "cat1", "mar.jpg"))
        assert image_format == "JPEG"
        image_format = ImageUtils.get_image_size(join(source_path, "cat1", "mar.exe"))
        assert image_format is None

    @pytest.mark.parametrize(
        "size, result",
        [
            ((276, 397), "portrait"),
            ((397, 276), "landscape"),
            ((100, 100), "square"),
            ((0, 0), None),
            ((0, 256), None),
            ((265, 0), None),
            ((265, -10), None),
        ],
    )
    @staticmethod
    def test_get_image_format_type(size, result):
        """Test get_image_format_type method"""
        image_format = ImageUtils.get_image_format_type(image_size=size)
        assert image_format == result

    @pytest.mark.parametrize(
        "filepath, image_size, image_format, is_valid, result",
        [
            (
                join(HelperTest.get_source_path(), "cat1", "mar.jpg"),
                True,
                True,
                True,
                {"image_size": (276, 397), "image_format": "JPEG", "is_valid": True},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.jpg"),
                False,
                True,
                True,
                {"image_format": "JPEG", "is_valid": True},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.jpg"),
                True,
                False,
                True,
                {"image_size": (276, 397), "is_valid": True},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.jpg"),
                True,
                True,
                False,
                {"image_size": (276, 397), "image_format": "JPEG"},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.exe"),
                True,
                True,
                True,
                {"image_size": None, "image_format": None, "is_valid": False},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.exe"),
                False,
                True,
                True,
                {"image_format": None, "is_valid": False},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.exe"),
                True,
                False,
                True,
                {"image_size": None, "is_valid": False},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.exe"),
                True,
                True,
                False,
                {"image_size": None, "image_format": None},
            ),
            (
                join(HelperTest.get_source_path(), "cat1", "mar.exe"),
                False,
                False,
                False,
                None,
            ),
        ],
    )
    @staticmethod
    def test_get_image_info(filepath, image_size, image_format, is_valid, result):
        """Test get_image_info method"""
        image_info = ImageUtils.get_image_info(
            filepath=filepath,
            image_size=image_size,
            image_format=image_format,
            is_valid=is_valid,
        )
        assert image_info == result

    @pytest.mark.parametrize(
        "size, result",
        [
            ((276, 397), True),
            ((397, 276), True),
            ((100, 100), True),
            ((100.25, 100.36), True),
            ((0, 0), False),
            ((0, 256), False),
            ((265, 0), False),
            ((265, -10), False),
        ],
    )
    @staticmethod
    def test_is_valid_size(size, result):
        """Test is_valid_size method"""
        image_format = ImageUtils.is_valid_size(size=size)
        assert image_format == result

    @pytest.mark.parametrize(
        "size, fixed_width, fixed_height, result",
        [
            ((276, 397), 250, 400, (250, 359.601)),
            ((276, 397), 250, 350, (243.325, 350)),
            ((250, 250), 180, 180, (180, 180)),
            ((800, 400), 250, 400, (250, 125.0)),
            ((400, 400), 250, 400, (250, 250)),
            ((100, 100), 250, 400, (250, 250)),
            ((100, 100), 250, None, (250, 250)),
            ((100, 100), None, 400, (400, 400)),
        ],
    )
    @staticmethod
    def test_get_new_scale(size, fixed_width, fixed_height, result):
        """Test get_new_scale method"""
        scale_size = ImageUtils.get_new_scale(
            size=size, fixed_width=fixed_width, fixed_height=fixed_height
        )
        assert scale_size == result

    @pytest.mark.parametrize(
        "size, fixed_width, fixed_height",
        [
            (("a", 397), 250, 400),
            ((32, "a"), 250, 400),
            ((50, -10), 250, 400),
            ((50, 0), 250, 400),
            ((50, 50), -50, 400),
            ((50, 50), 0, 400),
            ((50, 50), 250, -400),
            ((50, 50), 250, 0),
            ((50, 50), -10, None),
            ((50, 50), None, -10),
            ((50, 50), None, None),
        ],
    )
    @staticmethod
    def test_invalid_get_new_scale(size, fixed_width, fixed_height):
        """Test get_new_scale method"""
        with pytest.raises(ValueError):
            ImageUtils.get_new_scale(
                size=size, fixed_width=fixed_width, fixed_height=fixed_height
            )
