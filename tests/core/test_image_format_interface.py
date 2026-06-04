"""Tests for imgtools_m8.core.Image_format_interface."""

import pytest

from imgtools_m8.core.Image_format_interface import ImageFormatInterface


class TestImageFormatInterface:
    def test_load_image_raises(self):
        obj = ImageFormatInterface()
        with pytest.raises(NotImplementedError):
            obj.load_image("path.jpg")

    def test_save_image_raises(self):
        obj = ImageFormatInterface()
        with pytest.raises(NotImplementedError):
            obj.save_image("path.jpg")

    def test_get_image_format_raises(self):
        obj = ImageFormatInterface()
        with pytest.raises(NotImplementedError):
            obj.get_image_format()
