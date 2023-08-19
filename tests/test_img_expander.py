"""
ImageExpander unittest class.

Use pytest package.
"""
import pytest
from imgtools_m8.img_expander import ImageExpander
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.exceptions import SettingInvalidException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestImageExpander:

    def setup_method(self):
        """
        Setup any state tied to the execution of the given function.

        Invoked for every test function in the module.
        """
        self.obj = ImageExpander()

    def test_set_model_conf(self):
        """Test has_conf method"""
        assert self.obj.set_model_conf({
            'path': ImageToolsHelper.get_package_models_path(),
            'model_name': 'edsr',
            'scale': 2
        }) is True
        assert self.obj.set_model_conf() is True
        assert self.obj.set_model_conf({
            'scale': 3
        }) is True
        assert self.obj.set_model_conf({
            'path': ImageToolsHelper.get_package_models_path(),
            'scale': 4
        }) is True
