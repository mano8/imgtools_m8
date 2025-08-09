"""
Utility class for OpenCV operations.
"""
from os.path import isfile, join, dirname
from typing import Optional
import logging

import cv2
from numpy import ndarray
from ve_utils.utils import UType as Ut


__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "2.0.0"

logging.basicConfig()
logger = logging.getLogger("imgTools_m8")
# pylint: disable=no-member


class CvUtils:
    """
    Utility class for OpenCV operations.
    """
    @staticmethod
    def read_image(source_path: str) -> Optional[ndarray]:
        """
        Read and load an image from the specified source path.

        Example:
            >>> img = ImageTools.read_image("image.jpg")
            >>> type(img)
            >>> <class 'numpy.ndarray'>
        """
        img_src = None
        if Ut.is_str(source_path, not_null=True) \
                and isfile(source_path):
            img_src = cv2.imread(source_path)
        return img_src

    @staticmethod
    def get_package_models_path() -> Optional[str]:
        """
        Get the path to the package models' directory.

        :return:
            The path to the package models' directory,
            or None if not found.
        :rtype: Optional[str]

        Example:
            >>> ImageToolsHelper.get_package_models_path()
        '/path/to/package/models'
        """
        return join(dirname(__file__), 'models')
