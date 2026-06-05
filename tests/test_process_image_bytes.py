"""Tests for the in-memory ``process_image`` bytes API.

Use pytest package.
"""

import io
from os.path import join

import pytest
from PIL import Image

from imgtools_m8.image_process import process_image
from imgtools_m8.results import VariantResult

from .helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


# mar.jpg is a real portrait fixture (276x397) — never hardcode pixels blindly.
MAR_PATH = join(HelperTest.get_source_path(), "mar.jpg")


def _mar_bytes() -> bytes:
    """Return the raw bytes of the portrait mar.jpg fixture."""
    with open(MAR_PATH, "rb") as fh:
        return fh.read()


def _rgba_png_bytes() -> bytes:
    """Return PNG bytes of an RGBA image (has an alpha channel)."""
    img = Image.new("RGBA", (60, 40), (255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Aspect ratio (no hardcoded pixels — derive from the real fixture)
# ---------------------------------------------------------------------------


class TestAspectRatio:
    def test_fixed_width_preserves_aspect_ratio(self):
        with Image.open(MAR_PATH) as src:
            orig_w, orig_h = src.size
        results = process_image(
            _mar_bytes(),
            [{"image_size": {"fixed_width": 200}, "formats": [{"ext": "WEBP"}]}],
        )
        assert len(results) == 1
        variant = results[0]
        assert variant.width == 200
        assert variant.height == round(orig_h * (200 / orig_w))
        assert variant.format == "WEBP"
        assert isinstance(variant, VariantResult)
        assert isinstance(variant.data, bytes)
        assert variant.size_bytes == len(variant.data)


# ---------------------------------------------------------------------------
# Decode / validation edge cases
# ---------------------------------------------------------------------------


class TestDecodeAndOptions:
    def test_invalid_bytes_raise_value_error(self):
        with pytest.raises(ValueError):
            process_image(
                b"definitely not an image",
                [{"image_size": {"fixed_width": 50}, "formats": [{"ext": "JPEG"}]}],
            )

    def test_empty_options_return_empty_list(self):
        assert process_image(_mar_bytes(), []) == []


# ---------------------------------------------------------------------------
# Colour-mode conversion (RGBA source -> JPEG)
# ---------------------------------------------------------------------------


class TestColorModeConversion:
    def test_rgba_source_encoded_as_jpeg(self):
        results = process_image(
            _rgba_png_bytes(),
            [{"formats": [{"ext": "JPEG", "quality": 80}]}],
        )
        assert len(results) == 1
        variant = results[0]
        assert variant.format == "JPEG"
        # JPEG cannot hold alpha — decoded variant must be alpha-free.
        with Image.open(io.BytesIO(variant.data)) as decoded:
            assert decoded.format == "JPEG"
            assert decoded.mode in ("RGB", "L")


# ---------------------------------------------------------------------------
# max_byte_size is honoured
# ---------------------------------------------------------------------------


class TestMaxByteSize:
    def test_max_byte_size_constrains_output(self):
        max_bytes = 3_000
        results = process_image(
            _mar_bytes(),
            [
                {
                    "image_size": {"fixed_width": 200},
                    "max_byte_size": max_bytes,
                    "formats": [{"ext": "JPEG", "quality": 90}],
                }
            ],
        )
        assert len(results) == 1
        assert results[0].size_bytes <= max_bytes


# ---------------------------------------------------------------------------
# name label: caller-supplied vs derived stem
# ---------------------------------------------------------------------------


class TestNameLabel:
    def test_name_supplied_is_used(self):
        results = process_image(
            _mar_bytes(),
            [
                {
                    "name": "thumbnail",
                    "image_size": {"fixed_width": 200},
                    "formats": [{"ext": "WEBP"}],
                }
            ],
        )
        assert results[0].name == "thumbnail"

    def test_name_unset_derives_stem(self):
        results = process_image(
            _mar_bytes(),
            [{"image_size": {"fixed_width": 200}, "formats": [{"ext": "WEBP"}]}],
        )
        variant = results[0]
        assert variant.name == f"image_{variant.width}x{variant.height}"


# ---------------------------------------------------------------------------
# Multi-format option yields multiple results
# ---------------------------------------------------------------------------


class TestMultiFormat:
    def test_multiple_formats_yield_multiple_results(self):
        results = process_image(
            _mar_bytes(),
            [
                {
                    "image_size": {"fixed_width": 120},
                    "formats": [
                        {"ext": "JPEG", "quality": 75},
                        {"ext": "WEBP", "quality": 75},
                        {"ext": "PNG"},
                    ],
                }
            ],
        )
        assert len(results) == 3
        assert {r.format for r in results} == {"JPEG", "WEBP", "PNG"}
        # All variants share the resized dimensions and derived label.
        assert {(r.width, r.height) for r in results} == {(120, round(397 * 120 / 276))}
        assert len({r.name for r in results}) == 1
