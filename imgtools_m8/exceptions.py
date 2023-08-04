"""
ImgTools_m8 Exceptions.

Contain Exception trowed in ImgTools_m8 package.
"""
__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class ImgToolsException(Exception):
    """
    core exception.
    """


class SettingInvalidException(ImgToolsException):
    """
    Some data must match the expected value/type
    """
