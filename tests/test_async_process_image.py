"""Tests for the async in-memory bytes API wrappers.

The coroutines are driven from ordinary sync tests via ``asyncio.run`` so the
suite needs no extra test dependency (no ``pytest-asyncio``). Each case proves
the wrapper strictly delegates to the synchronous ``process_image`` — same
results, same exceptions.
"""

import asyncio
from os.path import join

import pytest

from imgtools_m8.async_api import process_image_async, process_images_async
from imgtools_m8.image_process import process_image
from imgtools_m8.results import VariantResult

from .helper import HelperTest

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


MAR_PATH = join(HelperTest.get_source_path(), "mar.jpg")


def _mar_bytes() -> bytes:
    """Return the raw bytes of the portrait mar.jpg fixture."""
    with open(MAR_PATH, "rb") as fh:
        return fh.read()


_WEBP_OPTS = [{"image_size": {"fixed_width": 200}, "formats": [{"ext": "WEBP"}]}]


def _assert_variants_equal(
    async_results: list[VariantResult], sync_results: list[VariantResult]
) -> None:
    """Assert two variant lists are byte-for-byte identical."""
    assert len(async_results) == len(sync_results)
    for a, s in zip(async_results, sync_results):
        assert a.data == s.data  # full byte-equality: strongest delegation proof
        assert a.name == s.name
        assert a.width == s.width
        assert a.height == s.height
        assert a.size_bytes == s.size_bytes
        assert a.format == s.format


# ---------------------------------------------------------------------------
# process_image_async — single image
# ---------------------------------------------------------------------------


class TestProcessImageAsync:
    def test_parity_with_sync(self):
        src = _mar_bytes()
        async_results = asyncio.run(process_image_async(src, _WEBP_OPTS))
        sync_results = process_image(src, _WEBP_OPTS)
        _assert_variants_equal(async_results, sync_results)
        assert isinstance(async_results[0], VariantResult)

    def test_invalid_bytes_raise_value_error(self):
        with pytest.raises(ValueError):
            asyncio.run(
                process_image_async(
                    b"definitely not an image",
                    [{"image_size": {"fixed_width": 50}, "formats": [{"ext": "JPEG"}]}],
                )
            )

    def test_exception_parity_same_message(self):
        bad = b"definitely not an image"
        opts = [{"image_size": {"fixed_width": 50}, "formats": [{"ext": "JPEG"}]}]
        with pytest.raises(ValueError) as sync_exc:
            process_image(bad, opts)
        with pytest.raises(ValueError) as async_exc:
            asyncio.run(process_image_async(bad, opts))
        assert str(sync_exc.value) == str(async_exc.value)

    def test_empty_options_return_empty_list(self):
        assert asyncio.run(process_image_async(_mar_bytes(), [])) == []

    def test_model_conf_passthrough(self):
        # Non-DNN option path: model_conf is forwarded but unused, matching how
        # the sync tests avoid requiring the model file on disk.
        src = _mar_bytes()
        model_conf = {"path": "/nonexistent", "model_name": "edsr", "scale": 4}
        async_results = asyncio.run(process_image_async(src, _WEBP_OPTS, model_conf))
        sync_results = process_image(src, _WEBP_OPTS, model_conf)
        _assert_variants_equal(async_results, sync_results)


# ---------------------------------------------------------------------------
# process_images_async — concurrent batch
# ---------------------------------------------------------------------------


class TestProcessImagesAsync:
    def test_batch_order_and_shape(self):
        src = _mar_bytes()
        sources = [src, src, src]
        batches = asyncio.run(process_images_async(sources, _WEBP_OPTS))
        assert len(batches) == 3
        expected = process_image(src, _WEBP_OPTS)
        for inner in batches:
            _assert_variants_equal(inner, expected)

    def test_empty_batch_returns_empty_list(self):
        assert asyncio.run(process_images_async([], _WEBP_OPTS)) == []

    def test_batch_error_propagates(self):
        sources = [_mar_bytes(), b"not an image"]
        with pytest.raises(ValueError):
            asyncio.run(process_images_async(sources, _WEBP_OPTS))
