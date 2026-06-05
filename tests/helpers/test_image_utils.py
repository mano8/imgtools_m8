"""
ImageToolsHelper unittest class.

Use pytest package.
"""

import os
from os.path import join

import pytest
from PIL import Image

from imgtools_m8.helpers.image_utils import ImageUtils
from imgtools_m8.schemas.conf_schema import JpegFormat

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
        image_format = ImageUtils.get_image_format(join(source_path, "cat1", "mar.exe"))
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


class TestGetCenterCropBox:
    def test_valid_crop(self):
        box = ImageUtils.get_center_crop_box((200, 100), 100, 50)
        left, upper, right, lower = box
        assert right - left == 100
        assert lower - upper == 50

    def test_invalid_original_size(self):
        with pytest.raises(ValueError):
            ImageUtils.get_center_crop_box((0, 0), 50, 50)

    def test_invalid_target_size(self):
        with pytest.raises(ValueError):
            ImageUtils.get_center_crop_box((200, 100), 0, 50)

    def test_target_exceeds_original(self):
        with pytest.raises(ValueError):
            ImageUtils.get_center_crop_box((100, 100), 200, 50)


class TestResizeImage:
    def test_resize_with_aspect_ratio(self, tmp_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        dest = str(tmp_path / "out.jpg")
        result = ImageUtils.resize_image(src, dest, 50, 50, maintain_aspect_ratio=True)
        assert result is True
        assert os.path.isfile(dest)

    def test_resize_without_aspect_ratio(self, tmp_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        dest = str(tmp_path / "out.jpg")
        result = ImageUtils.resize_image(src, dest, 50, 50, maintain_aspect_ratio=False)
        assert result is True

    def test_invalid_path_returns_false(self, tmp_path):
        result = ImageUtils.resize_image(
            "/nonexistent.jpg", str(tmp_path / "out.jpg"), 50, 50
        )
        assert result is False


class TestGetFormatKwargs:
    def test_returns_dict_for_valid(self):
        fmt = JpegFormat(quality=80)
        result = ImageUtils.get_format_kwargs("JPEG", fmt)
        assert isinstance(result, dict)
        assert "quality" in result

    def test_returns_none_for_none_args(self):
        assert ImageUtils.get_format_kwargs("JPEG", None) is None


class TestConvertImageFormat:
    def test_convert_to_webp(self, tmp_path):
        # Use format_args=None to avoid None PIL kwargs issue
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        dest = str(tmp_path / "out.webp")
        assert ImageUtils.convert_image_format(src, dest, "WEBP", None) is True
        assert os.path.isfile(dest)

    def test_convert_to_png(self, tmp_path):
        # Use format_args=None; RGB→PNG conversion hits line 375 (RGBA conversion)
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        dest = str(tmp_path / "out.png")
        assert ImageUtils.convert_image_format(src, dest, "PNG", None) is True

    def test_convert_rgba_to_jpeg(self, tmp_path):
        # RGBA → JPEG hits line 375 (src.convert("RGB"))
        src = str(tmp_path / "rgba.png")
        Image.new("RGBA", (20, 20)).save(src)
        dest = str(tmp_path / "out.jpg")
        assert ImageUtils.convert_image_format(src, dest, "JPEG", None) is True

    def test_invalid_format_returns_false(self, tmp_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        dest = str(tmp_path / "out.bmp")
        fmt = JpegFormat()
        assert ImageUtils.convert_image_format(src, dest, "BMP", fmt) is False

    def test_invalid_format_type_returns_false(self, tmp_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        dest = str(tmp_path / "out.jpg")
        assert ImageUtils.convert_image_format(src, dest, 123, None) is False

    def test_convert_rgba_to_png_no_mode_conversion(self, tmp_path):
        # RGBA source → PNG: mode already in {"RGBA"} → else branch (out = src)
        src = str(tmp_path / "rgba.png")
        Image.new("RGBA", (20, 20)).save(src)
        dest = str(tmp_path / "out.png")
        assert ImageUtils.convert_image_format(src, dest, "PNG", None) is True

    def test_invalid_source_returns_false(self, tmp_path):
        dest = str(tmp_path / "out.jpg")
        fmt = JpegFormat(quality=80)
        assert ImageUtils.convert_image_format("/bad.jpg", dest, "JPEG", fmt) is False
