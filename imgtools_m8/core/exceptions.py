"""
ImgTools_m8 Exceptions.

This module contains custom exceptions used in the ImgTools_m8 package.
"""

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache Software License"
__status__ = "Production"
__version__ = "1.0.0"


class ImgToolsException(Exception):
    """
    Base exception class for the ImgTools_m8 package.

    This is the base class for all exceptions raised
    within the ImgTools_m8 package.
    It provides a common interface for handling errors specific to ImgTools_m8.
    """


class SettingInvalidException(ImgToolsException):
    """
    Exception for invalid settings or configurations.

    This exception is raised when a setting
    or configuration provided to ImgTools_m8
    is invalid or does not match the expected value or type.
    """


class ModelNotFoundError(ImgToolsException):
    """
    Exception for a missing super-resolution model file.

    Raised when DNN upscaling is requested but the resolved model
    file is absent on disk. The message hints at running
    ``imgtools download-models`` to fetch the models.
    """
