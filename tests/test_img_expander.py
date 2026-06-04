"""
ImageExpander unittest class.

Use pytest package.
"""

import os.path as _path

import pytest

from imgtools_m8.core.exceptions import ImgToolsException
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.helpers.model_conf import ScaleSelector
from imgtools_m8.img_expander import ImageExpander

from .helper import HelperTest

cv2 = pytest.importorskip("cv2")

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

    def test_set_model_conf(self):
        """Test set_model_conf method."""
        assert (
            self.obj.set_model_conf(
                {
                    "path": ImageToolsHelper.get_package_models_path(),
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
                    "path": ImageToolsHelper.get_package_models_path(),
                    "scale": 4,
                }
            )
            is True
        )

    def test_many_image_upscale(self):
        """Test many_image_upscale method."""
        image = cv2.imread(
            _path.join(HelperTest.get_source_path(), "recien_llegado_min.jpg")
        )
        resized = self.obj.many_image_upscale(image=image, nb_upscale=1, scale=3)
        assert ImageToolsHelper.get_image_size(
            image
        ) != ImageToolsHelper.get_image_size(resized)
        with pytest.raises(ImgToolsException):
            self.obj.many_image_upscale(image=image, nb_upscale=1, scale=-3)

    def test_init_sr_raises_when_cv2_unavailable(self, monkeypatch):
        """init_sr should raise when CV2_AVAILABLE is False."""
        import imgtools_m8.img_expander as expander_mod

        monkeypatch.setattr(expander_mod, "CV2_AVAILABLE", False)
        with pytest.raises(ImgToolsException):
            self.obj.init_sr()
