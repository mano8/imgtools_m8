"""
ImageExpander unittest class.

Use pytest package.
"""
import pytest
import os
from imgtools_m8.img_expander import ImageExpander
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
        self.models_path = os.path.join('.', 'imgtools_m8', 'models')
        self.source_path = os.path.join('.', 'tests', 'dummy_dir')
        self.obj = ImageExpander()

    def test_set_model_conf(self):
        """Test has_conf method"""
        assert self.obj.set_model_conf({
            'path': self.models_path,
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsr',
            'scale': 2
        }) is True
        assert self.obj.set_model_conf() is True
        assert self.obj.set_model_conf({
            'file_name': 'EDSR_x2.pb'
        }) is True
        assert self.obj.set_model_conf({
            'path': self.models_path,
            'file_name': 'EDSR_x4.pb'
        }) is True

        with pytest.raises(SettingInvalidException):
            self.obj.set_model_conf({
                'file_name': 'EDSR_x4'
            })

    @staticmethod
    def test_get_models_list():
        """Test get_models_list method"""
        models_list = ImageExpander.get_models_list(
            os.path.join('.', 'imgtools_m8', 'models')
        )
        assert len(models_list) > 0
        assert 'EDSR_x2.pb' in models_list

    @staticmethod
    def test_get_model_scale():
        """Test get_model_scale method"""
        assert ImageExpander.get_model_scale("") == 0
        assert ImageExpander.get_model_scale('EDSR_x2.pb') == 2
        assert ImageExpander.get_model_scale('EDSR_x6.pb') == 6

    @staticmethod
    def test_get_model_name():
        """Test get_model_name method"""
        assert ImageExpander.get_model_name("") is None
        assert ImageExpander.get_model_name('EDSR_x2.pb') == 'edsr'
        assert ImageExpander.get_model_name('sb2_x6.pb') == 'sb2'

    @staticmethod
    def test_is_model_conf():
        """Test is_model_conf method"""
        assert ImageExpander.is_model_conf({
            'path': os.path.join('.', 'imgtools_m8', 'models'),
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsr',
            'scale': 2
        }) is True
        assert ImageExpander.is_model_conf({
            'path': '/bad_path',  # bad path
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsr',
            'scale': 2
        }) is False
        assert ImageExpander.is_model_conf({
            'path': os.path.join('.', 'imgtools_m8', 'models'),
            'file_name': 'EDSR_x2',  # bad file_name without extension
            'model_name': 'edsr',
            'scale': 2
        }) is False
        assert ImageExpander.is_model_conf({}) is False
        assert ImageExpander.is_model_conf({
            'path': os.path.join('.', 'imgtools_m8', 'models'),
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsrBad',  # bad model_name must be part of file_name
            'scale': 2
        }) is False
        assert ImageExpander.is_model_conf({
            'path': os.path.join('.', 'imgtools_m8', 'models'),
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsr',
            'scale': 3  # bad scale != of file_name
        }) is False
        assert ImageExpander.is_model_conf({
            'path': os.path.join('.', 'imgtools_m8', 'models'),
            'file_name': 'EDSR_x12.pb',
            'model_name': 'edsr',
            'scale': 12  # bad scale > 8 (2 >= scale <= 8)
        }) is False
        assert ImageExpander.is_model_conf({
            'path': os.path.join('.', 'imgtools_m8', 'models'),
            'file_name': 'EDSR_x1.pb',
            'model_name': 'edsr',
            'scale': 1  # bad scale < 2 (2 >= scale <= 8)
        }) is False
