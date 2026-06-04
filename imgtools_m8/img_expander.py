"""
Image Expander class

This module provides a tool for expanding images
using Super-Resolution techniques.
"""

import os
from typing import Optional

try:
    from cv2 import dnn_superres

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    dnn_superres = None  # type: ignore[assignment]

from imgtools_m8.core.exceptions import ImgToolsException
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.helpers.model_conf import ModelConf, ScaleSelector
from imgtools_m8.schemas.upscaler_schema import UpscaleModelDict

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"

# pylint: disable=no-member, c-extension-no-member


class ImageExpander:
    """
    Image Expander Tool

    This class provides methods for expanding images
    using Super-Resolution techniques.
    """

    def __init__(
        self,
        model_conf: Optional[UpscaleModelDict] = None,
    ):
        """
        Initialize the ImageExpander instance.

        :param model_conf: Configuration for the Super-Resolution model.
        :type model_conf: dict, optional
        """
        self.model_conf: Optional[ModelConf] = None
        self.sr = None
        self.set_model_conf(model_conf)

    def is_ready(self) -> bool:
        """
        Check if the ImageExpander is ready to perform image expansion.

        :return: True if ready, False otherwise.
        :rtype: bool

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander(model_config)
            >>> expander.is_ready()
            True
        """
        return self.has_model_conf() and self.sr is not None

    def has_model_conf(self) -> bool:
        """
        Check if the ImageExpander instance has a valid model configuration.

        :return: True if model configuration is valid, False otherwise.
        :rtype: bool

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander(model_config)
            >>> expander.has_model_conf()
            True
        """
        return self.model_conf is not None and self.model_conf.is_ready()

    def set_model_conf(self, model_conf: Optional[UpscaleModelDict] = None) -> bool:
        """
        Set the model configuration for the ImageExpander.

        :param model_conf: The model configuration dictionary.
        :type model_conf: dict, optional

        :return:
            True if the model configuration is set successfully,
            False otherwise.
        :rtype: bool

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander()
            >>> expander.set_model_conf(model_config)
            True
        """
        model_path: Optional[str] = ImageToolsHelper.get_package_models_path()
        model_name: str = "edsr"
        scale: int = 2
        scale_selector: ScaleSelector = ScaleSelector.AUTO_SCALE
        if isinstance(model_conf, dict) and model_conf:
            raw_path = model_conf.get("path")
            if isinstance(raw_path, str) and ModelConf.is_model_path(raw_path):
                model_path = raw_path

            raw_name = model_conf.get("model_name")
            if isinstance(raw_name, str) and ModelConf.is_model_name(raw_name):
                model_name = raw_name

            raw_scale = model_conf.get("scale")
            if isinstance(raw_scale, int) and ModelConf.is_scale(
                model_path=model_path,
                model_name=model_name,
                scale=raw_scale,
            ):
                scale = raw_scale
                scale_selector = ScaleSelector.FIXED_SCALE

            raw_selector = model_conf.get("scale_selector")
            if isinstance(raw_selector, ScaleSelector) and ModelConf.is_scale_selector(
                raw_selector
            ):
                scale_selector = raw_selector

        self.model_conf = ModelConf(
            model_path=model_path,
            model_name=model_name,
            scale=scale,
            scale_selector=scale_selector,
        )
        test = self.model_conf.is_ready()
        return test

    def init_sr(self):
        """
        Initialize the Super-Resolution model.

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander(model_config)
            >>> expander.init_sr()
        """
        if not CV2_AVAILABLE:
            raise ImgToolsException(
                "DNN upscaling requires opencv-contrib-python. "
                "Install with: pip install imgtools_m8[dnn]"
            )
        self.sr = dnn_superres.DnnSuperResImpl_create()

    def load_model(self):
        """
        Load the super-resolution model using
        the configured model configuration.

        :return: True if the model is loaded successfully, False otherwise.
        :rtype: bool

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander(model_config)
            >>> expander.load_model()
            True
        """
        test = False
        if self.has_model_conf():
            mod_path = os.path.join(
                self.model_conf.get_path(), self.model_conf.get_file_name()
            )
            if os.path.isfile(mod_path):
                self.sr.readModel(mod_path)
                # Set the desired model and scale
                # to get correct pre- and post-processing
                self.sr.setModel(
                    self.model_conf.get_model_name(), self.model_conf.get_scale()
                )
                test = True
        return test

    def upscale_image(self, image: object):
        """
        Upscale the input image using the loaded super-resolution model.

        :param image: The input image as a NumPy array.

        :return: The upscaled image.
        :rtype: object

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander(model_config)
            >>> expander.load_model()
            >>> input_image = ...
            >>> upscaled_image = expander.upscale_image(input_image)
        """
        if image is not None and self.sr is not None:
            image = self.sr.upsample(image)
        return image

    def many_image_upscale(
        self, image: object, nb_upscale: int, scale: Optional[int] = None
    ) -> Optional[object]:
        """
        Upscale an image multiple times using the super-resolution model.

        :param image: The input image as a NumPy array.
        :param nb_upscale: The number of times to upscale the image.
        :param scale: The model scale to use.

        :return: The final upscaled image after multiple upscaling operations.
        :rtype: object or None

        Example:
            >>> model_config = {
                'model_path': 'path/to/models',
                'model_name': 'edsr',
                'scale': 2
            }
            >>> expander = ImageExpander(model_config)
            >>> expander.load_model()
            >>> input_image = ...
            >>> final_upscaled_image = expander.many_image_upscale(
                input_image,
                nb_upscale=3
            )
        """
        max_upscale = 10
        if (
            image is not None
            and isinstance(nb_upscale, int)
            and 1 <= nb_upscale <= max_upscale
            and self.model_conf is not None
        ):
            is_scale = ModelConf.is_scale(
                model_path=self.model_conf.model_path,
                model_name=self.model_conf.model_name,
                scale=scale,
            )
            if isinstance(scale, int) and not is_scale:
                raise ImgToolsException("Fatal Error: Invalid model scale selected.")

            if is_scale and self.model_conf.scale != scale:
                self.model_conf.set_scale(scale)
                if not self.is_ready():
                    self.init_sr()
                self.load_model()

            counter = 0
            while counter < nb_upscale and counter <= max_upscale:
                image = self.upscale_image(image)
                counter += 1
        return image
