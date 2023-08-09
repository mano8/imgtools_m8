"""
Helper unittest class.
"""
import os
from imgtools_m8.helper import ImageToolsHelper

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class HelperTest:

    @staticmethod
    def get_source_path() -> str or None:
        """Get package models' path."""
        return os.path.join(os.path.dirname(__file__), 'sources_test')

    @staticmethod
    def get_output_path() -> str or None:
        """Get package models' path."""
        return os.path.join(os.path.dirname(__file__), 'output_test')
