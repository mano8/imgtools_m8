"""
ImageProcessing unittest class.

Use pytest package.
"""

import os
from os.path import join

import pytest
from PIL import Image

from imgtools_m8.image_process import ImageProcessing
from imgtools_m8.schemas.conf_schema import OutputSize

from .helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _conf(source_path=None, output_options=None, **kwargs):
    """Build a minimal valid conf dict."""
    return {
        "source_path": source_path or HelperTest.get_source_path(),
        "output_path": HelperTest.get_output_path(),
        "output_options": output_options
        or [
            {
                "image_size": {"fixed_width": 35, "fixed_height": 22},
                "allow_upscale": False,
                "max_byte_size": 1024 * 1024,
                "formats": [{"ext": "WEBP", "quality": 80}],
            }
        ],
        **kwargs,
    }


def _obj(source_path=None, output_options=None, **kwargs):
    return ImageProcessing(conf=_conf(source_path, output_options, **kwargs))


# ---------------------------------------------------------------------------
# Guard checks
# ---------------------------------------------------------------------------


class TestImageProcessingGuards:
    """Boolean guard methods."""

    def test_has_conf(self):
        assert _obj().has_conf() is True

    def test_has_input_file(self):
        obj = _obj(source_path=join(HelperTest.get_source_path(), "cat1", "mar.jpg"))
        assert obj.has_input_file() is True

    def test_has_input_dir(self):
        assert _obj().has_input_dir() is True

    def test_has_output_options(self):
        assert _obj().has_output_options() is True

    def test_has_image_sizes(self):
        obj = _obj()
        assert obj.has_image_sizes(obj.conf.output_options[0]) is True

    def test_has_max_bytes(self):
        obj = _obj()
        assert obj.has_max_bytes(obj.conf.output_options[0]) is True

    def test_has_output_formats(self):
        obj = _obj()
        assert obj.has_output_formats(obj.conf.output_options[0]) is True

    def test_has_output_format(self):
        obj = _obj()
        assert obj.has_output_format(obj.conf.output_options[0].formats[0]) is True


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


class TestOutputStem:
    def test_basic(self):
        stem = ImageProcessing._get_output_stem("photo.jpg", (800, 600))
        assert stem == "photo_800x600"

    def test_subpath(self):
        stem = ImageProcessing._get_output_stem("/some/dir/image.png", (100, 200))
        assert stem == "image_100x200"


class TestGetOutputSubdir:
    def test_flatten(self, output_path):
        result = ImageProcessing._get_output_subdir(
            output_path, ["a", "b"], flatten=True
        )
        assert result == output_path

    def test_no_subdirs(self, output_path):
        result = ImageProcessing._get_output_subdir(output_path, None, flatten=False)
        assert result == output_path

    def test_with_subdirs(self, output_path):
        result = ImageProcessing._get_output_subdir(
            output_path, ["cat1", "sub"], flatten=False
        )
        assert result == join(output_path, "cat1", "sub")
        assert os.path.isdir(result)


class TestFitWithinBox:
    @pytest.mark.parametrize(
        "w,h,fw,fh,upscale,expected",
        [
            (400, 300, 200, 200, False, (200, 150)),
            (100, 100, 200, 200, False, (100, 100)),
            (100, 100, 200, 200, True, (200, 200)),
            (800, 400, 400, 300, False, (400, 200)),
            (400, 800, 400, 300, False, (150, 300)),
        ],
    )
    def test_variants(self, w, h, fw, fh, upscale, expected):
        assert ImageProcessing._fit_within_box(w, h, fw, fh, upscale) == expected


class TestResizeToFit:
    @pytest.mark.parametrize(
        "kwargs,orig,expected",
        [
            ({"fixed_width": 100}, (200, 400), (100, 200)),
            ({"fixed_height": 100}, (200, 400), (50, 100)),
            ({"fixed_size": 100}, (200, 400), (50, 100)),
            ({"fixed_downscale": 2}, (200, 400), (100, 200)),
            ({"fixed_upscale": 2}, (100, 200), (200, 400)),
            ({"fixed_width": 100, "fixed_height": 100}, (200, 400), (50, 100)),
        ],
    )
    def test_variants(self, kwargs, orig, expected):
        img = Image.new("RGB", orig)
        result = ImageProcessing._resize_to_fit(
            img, OutputSize(**kwargs), allow_upscale=True
        )
        assert result.size == expected

    def test_no_upscale_skips_larger_target(self):
        img = Image.new("RGB", (50, 50))
        result = ImageProcessing._resize_to_fit(
            img, OutputSize(fixed_width=200), allow_upscale=False
        )
        assert result.size == (50, 50)

    def test_no_constraint_returns_original(self):
        img = Image.new("RGB", (100, 100))
        result = ImageProcessing._resize_to_fit(img, OutputSize())
        assert result is img


# ---------------------------------------------------------------------------
# Integration: process_file / process_directory / run
# ---------------------------------------------------------------------------


class TestProcessFile:
    def test_valid_jpeg(self):
        obj = _obj(source_path=join(HelperTest.get_source_path(), "cat1", "mar.jpg"))
        assert (
            obj.process_file(
                source_path=obj.conf.source_path,
                info={"name": "mar.jpg"},
            )
            is True
        )

    def test_invalid_source_returns_false(self):
        obj = _obj()
        assert (
            obj.process_file(
                source_path="/nonexistent/path/image.jpg",
                info={"name": "image.jpg"},
            )
            is False
        )

    def test_multiple_formats(self, output_path):
        obj = ImageProcessing(
            conf={
                "source_path": join(HelperTest.get_source_path(), "cat1", "mar.jpg"),
                "output_path": output_path,
                "output_options": [
                    {
                        "image_size": {"fixed_width": 40},
                        "formats": [
                            {"ext": "JPEG", "quality": 75},
                            {"ext": "WEBP", "quality": 75},
                            {"ext": "PNG"},
                        ],
                    }
                ],
            }
        )
        assert (
            obj.process_file(
                source_path=join(HelperTest.get_source_path(), "cat1", "mar.jpg"),
                info={"name": "mar.jpg"},
            )
            is True
        )


class TestRun:
    def test_run_single_file(self, output_path):
        src = join(HelperTest.get_source_path(), "cat1", "mar.jpg")
        obj = ImageProcessing(
            conf={
                "source_path": src,
                "output_path": output_path,
                "output_options": [{"formats": [{"ext": "WEBP", "quality": 80}]}],
            }
        )
        assert obj.run() is True

    def test_run_directory(self, output_path):
        obj = ImageProcessing(
            conf={
                "source_path": join(HelperTest.get_source_path(), "good"),
                "output_path": output_path,
                "output_options": [{"formats": [{"ext": "JPEG", "quality": 80}]}],
            }
        )
        assert obj.run() is True

    def test_run_nonexistent_source(self, output_path):
        obj = ImageProcessing(
            conf={
                "source_path": "/nonexistent/path",
                "output_path": output_path,
                "output_options": [{"formats": [{"ext": "WEBP", "quality": 80}]}],
            }
        )
        assert obj.run() is False

    def test_run_with_subdirs(self, output_path):
        obj = ImageProcessing(
            conf={
                "source_path": HelperTest.get_source_path(),
                "output_path": output_path,
                "include_subdirs": True,
                "output_options": [{"formats": [{"ext": "WEBP", "quality": 80}]}],
            }
        )
        assert obj.run() is True


class TestEnforceMaxBytes:
    def test_jpeg_fits_under_limit(self, output_path):
        src = join(HelperTest.get_source_path(), "recien_llegado_min.jpg")
        max_bytes = 5_000
        obj = ImageProcessing(
            conf={
                "source_path": src,
                "output_path": output_path,
                "output_options": [
                    {
                        "max_byte_size": max_bytes,
                        "formats": [{"ext": "JPEG", "quality": 90}],
                    }
                ],
            }
        )
        assert obj.run() is True
        out_files = [
            f
            for f in os.listdir(output_path)
            if f.startswith("recien_llegado_min_") and f.endswith(".jpg")
        ]
        assert out_files, "No JPEG output produced"
        out_path = join(output_path, out_files[0])
        assert os.path.getsize(out_path) <= max_bytes
