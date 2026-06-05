"""
ImageExpander unittest class.

Use pytest package.
"""

import os
import os.path as _path
from unittest.mock import MagicMock

import numpy as np
import pytest

import imgtools_m8.img_expander as _mod
from imgtools_m8.core.exceptions import ImgToolsException
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.helpers.model_conf import ScaleSelector
from imgtools_m8.img_expander import ImageExpander

from .helper import HelperTest

_REPO_MODELS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "models",
    "opencv",
)

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"


class TestImageExpander:
    """ImageExpander unittest class."""

    def setup_method(self):
        """Invoked before every test function in the module."""
        self.obj = ImageExpander()

    # ------------------------------------------------------------------
    # set_model_conf — no cv2 needed
    # ------------------------------------------------------------------

    def test_set_model_conf(self):
        """Test set_model_conf method."""
        assert (
            self.obj.set_model_conf(
                {
                    "path": _REPO_MODELS,
                    "model_name": "edsr",
                    "scale": 2,
                    "scale_selector": ScaleSelector.AUTO_SCALE,
                }
            )
            is True
        )
        assert self.obj.set_model_conf() is True
        assert self.obj.set_model_conf({"scale": 3}) is True
        assert (
            self.obj.set_model_conf(
                {
                    "path": _REPO_MODELS,
                    "scale": 4,
                }
            )
            is True
        )

    # ------------------------------------------------------------------
    # init_sr — line 171 covered via mock; raise path without cv2
    # ------------------------------------------------------------------

    def test_init_sr_raises_when_cv2_unavailable(self, monkeypatch):
        """init_sr should raise when CV2_AVAILABLE is False."""
        monkeypatch.setattr(_mod, "CV2_AVAILABLE", False)
        with pytest.raises(ImgToolsException):
            self.obj.init_sr()

    def test_init_sr_with_mock_dnn(self, monkeypatch):
        """init_sr assigns sr when CV2_AVAILABLE is True (line 171)."""
        mock_sr = MagicMock()
        mock_dnn = MagicMock()
        mock_dnn.DnnSuperResImpl_create.return_value = mock_sr
        monkeypatch.setattr(_mod, "CV2_AVAILABLE", True)
        monkeypatch.setattr(_mod, "dnn_superres", mock_dnn)

        self.obj.init_sr()

        mock_dnn.DnnSuperResImpl_create.assert_called_once()
        assert self.obj.sr is mock_sr

    # ------------------------------------------------------------------
    # load_model — lines 192-204 covered via mock sr
    # ------------------------------------------------------------------

    def test_load_model_with_mock_sr(self):
        """load_model returns True when model file exists and sr is set."""
        mock_sr = MagicMock()
        self.obj.sr = mock_sr

        result = self.obj.load_model()

        assert result is True
        mock_sr.readModel.assert_called_once()
        mock_sr.setModel.assert_called_once()

    # ------------------------------------------------------------------
    # upscale_image — line 227 covered via mock sr
    # ------------------------------------------------------------------

    def test_upscale_image_with_mock_sr(self):
        """upscale_image delegates to sr.upsample when sr is set (line 227)."""
        mock_sr = MagicMock()
        expected = np.ones((10, 10, 3), dtype=np.uint8)
        mock_sr.upsample.return_value = expected
        self.obj.sr = mock_sr

        image = np.zeros((5, 5, 3), dtype=np.uint8)
        result = self.obj.upscale_image(image)

        mock_sr.upsample.assert_called_once_with(image)
        assert result is expected

    def test_upscale_image_no_sr_returns_unchanged(self):
        """upscale_image returns the original image when sr is None."""
        image = np.zeros((5, 5, 3), dtype=np.uint8)
        result = self.obj.upscale_image(image)
        assert result is image

    # ------------------------------------------------------------------
    # many_image_upscale — lines 257-282 covered via mocks
    # ------------------------------------------------------------------

    def test_many_image_upscale_invalid_scale_raises(self):
        """Raises ImgToolsException for an out-of-range scale (line 270)."""
        image = np.zeros((5, 5, 3), dtype=np.uint8)
        with pytest.raises(ImgToolsException):
            self.obj.many_image_upscale(image=image, nb_upscale=1, scale=-3)

    def test_many_image_upscale_scale_change_triggers_init_sr(self, monkeypatch):
        """When scale changes and sr is None, init_sr and load_model are called (lines 272-276)."""
        image = np.zeros((5, 5, 3), dtype=np.uint8)

        mock_sr = MagicMock()
        mock_sr.upsample.return_value = image

        init_sr_calls = []

        def _mock_init_sr():
            init_sr_calls.append(True)
            self.obj.sr = mock_sr

        monkeypatch.setattr(self.obj, "init_sr", _mock_init_sr)
        monkeypatch.setattr(self.obj, "load_model", MagicMock(return_value=True))

        result = self.obj.many_image_upscale(image=image, nb_upscale=1, scale=3)

        assert init_sr_calls, "init_sr should have been called (line 275)"
        assert result is image

    def test_many_image_upscale_scale_change_already_ready(self, monkeypatch):
        """When scale changes and sr is already set, only load_model is called (line 276)."""
        image = np.zeros((5, 5, 3), dtype=np.uint8)

        mock_sr = MagicMock()
        mock_sr.upsample.return_value = image
        self.obj.sr = mock_sr  # is_ready() → True → skip init_sr

        mock_load = MagicMock(return_value=True)
        monkeypatch.setattr(self.obj, "load_model", mock_load)

        result = self.obj.many_image_upscale(image=image, nb_upscale=1, scale=3)

        mock_load.assert_called_once()
        assert result is image

    def test_many_image_upscale_none_image_returns_none(self):
        """Returns None when image is None (short-circuits guard)."""
        assert self.obj.many_image_upscale(image=None, nb_upscale=1) is None

    # ------------------------------------------------------------------
    # test_many_image_upscale — real cv2 test (skipped when cv2 absent)
    # ------------------------------------------------------------------

    def test_many_image_upscale_real_cv2(self):
        """End-to-end test with real cv2; skipped when cv2 not installed."""
        cv2 = pytest.importorskip("cv2")
        image = cv2.imread(
            _path.join(HelperTest.get_source_path(), "recien_llegado_min.jpg")
        )
        resized = self.obj.many_image_upscale(image=image, nb_upscale=1, scale=3)
        assert ImageToolsHelper.get_image_size(
            image
        ) != ImageToolsHelper.get_image_size(resized)
        with pytest.raises(ImgToolsException):
            self.obj.many_image_upscale(image=image, nb_upscale=1, scale=-3)
