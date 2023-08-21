"""
ModelConf unittest class.

Use pytest package.
"""
import pytest
from ve_utils.utils import UType as Ut
from .helper import HelperTest
from imgtools_m8.process_conf import ProcessConf
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.exceptions import SettingInvalidException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestModelConf:

    def setup_method(self):
        """
        Setup any state tied to the execution of the given function.

        Invoked for every test function in the module.
        """
        output_formats = [
            {
                'fixed_width': 260,
                'fixed_height': 200,
                'formats': [
                    {'ext': '.jpg', 'quality': 80}
                ]
            }
        ]
        self.obj = ProcessConf(
            source_path=HelperTest.get_source_path(),
            output_path=HelperTest.get_output_path(),
            output_formats=output_formats
        )

    def test_is_ready(self):
        """Test is_ready method"""
        assert self.obj.is_ready() is True

    def test_set_source_path(self):
        """Test set_source_path method"""
        self.obj.source_path = None
        assert self.obj.has_source_path() is False
        assert self.obj.set_source_path(
            HelperTest.get_source_path()
        ) is True
        assert self.obj.get_source_path() == HelperTest.get_source_path()
        assert self.obj.has_source_path() is True
        assert self.obj.set_source_path('/bad_path') is False
        assert self.obj.has_source_path() is False

    def test_set_output_path(self):
        """Test set_output_path method"""
        self.obj.output_path = None
        assert self.obj.has_output_path() is False
        assert self.obj.set_output_path(
            HelperTest.get_output_path()
        ) is True
        assert self.obj.get_output_path() == HelperTest.get_output_path()
        assert self.obj.has_output_path() is True
        assert self.obj.set_output_path('/bad_path') is False
        assert self.obj.has_output_path() is False

    def test_set_output_formats(self):
        """Test set_output_formats method"""
        self.obj.output_formats = None
        assert self.obj.has_output_formats() is False
        assert self.obj.set_output_formats([
            {
                'formats': [
                    {'ext': '.jpg', 'quality': 80, 'progressive': 1, 'optimize': 1}
                ]
            },
            {
                'fixed_width': 260,
                'formats': [
                    {'ext': '.webp', 'quality': 80}
                ]
            },
            {
                'fixed_height': 260,
                'formats': [
                    {'ext': '.png', 'compression': 0}
                ]
            },
            {
                'fixed_size': 260,
                'formats': [
                    {'ext': '.png', 'compression': 0}
                ]
            },
            {
                'fixed_scale': 6,
                'formats': [
                    {'ext': '.png', 'compression': 0}
                ]
            }
        ]) is True
        assert self.obj.has_output_formats() is True
        with pytest.raises(SettingInvalidException):
            self.obj.set_output_formats([])
        assert self.obj.get_output_formats() is None
        error_values = [
            {'nop': '.webp'},
            {'ext': 'png'},
            {'ext': '.tar'},
            {'ext': '.pdf'},
            {'ext': '.png', 'compression': 10},
            {'ext': '.webp', 'quality': 101},
            {'ext': '.jpeg', 'quality': 101},
        ]
        with pytest.raises(SettingInvalidException):
            self.obj.set_output_formats(error_values)

    @staticmethod
    def test_is_fixed_width_or_height():
        """Test is_fixed_width_or_height method"""
        true_values = [
            {
                'fixed_width': 260,
                'fixed_height': 200
            },
            {'fixed_height': 200},
            {'fixed_width': 200}
        ]
        for data in true_values:
            assert ProcessConf.is_fixed_width_or_height(data) is True

        assert ProcessConf.is_fixed_width_or_height({}) is False

        error_values = [
            {
                'fixed_width': 0,
                'fixed_height': 260
            },
            {
                'fixed_width': 260,
                'fixed_height': 0
            },
            {
                'fixed_width': 260,
                'fixed_size': 260
            },
            {
                'fixed_width': 260,
                'fixed_scale': 2
            },
            {
                'fixed_height': 260,
                'fixed_size': 260
            },
            {
                'fixed_height': 260,
                'fixed_scale': 2
            },
            {'fixed_width': -1},
            {'fixed_height': -1}
        ]

        for data in error_values:
            with pytest.raises(SettingInvalidException):
                ProcessConf.is_fixed_width_or_height(data)

    @staticmethod
    def test_is_fixed_size():
        """Test is_fixed_size method"""
        true_values = [
            {'fixed_size': 260},
            {'fixed_size': 1}
        ]
        for data in true_values:
            assert ProcessConf.is_fixed_size(data) is True

        assert ProcessConf.is_fixed_size({}) is False

        error_values = [
            {
                'fixed_scale': 2,
                'fixed_size': 260
            },
            {
                'fixed_width': 260,
                'fixed_size': 260
            },
            {
                'fixed_height': 260,
                'fixed_size': 260
            },
            {'fixed_size': 0},
            {'fixed_size': -1}
        ]

        for data in error_values:
            with pytest.raises(SettingInvalidException):
                ProcessConf.is_fixed_size(data)

    @staticmethod
    def test_is_fixed_scale():
        """Test is_fixed_scale method"""
        true_values = [
            {'fixed_scale': 2},
            {'fixed_scale': 10}
        ]
        for data in true_values:
            assert ProcessConf.is_fixed_scale(data) is True

        assert ProcessConf.is_fixed_scale({}) is False

        error_values = [
            {
                'fixed_scale': 2,
                'fixed_size': 260
            },
            {
                'fixed_width': 260,
                'fixed_scale': 260
            },
            {
                'fixed_height': 260,
                'fixed_scale': 260
            },
            {'fixed_scale': 0},
            {'fixed_scale': -1}
        ]

        for data in error_values:
            with pytest.raises(SettingInvalidException):
                ProcessConf.is_fixed_scale(data)

    @staticmethod
    def test_set_output_size():
        """Test set_output_size method"""
        true_values = [
            {},
            {
                'fixed_height': 260,
                'fixed_width': 10
            },
            {
                'fixed_height': 260,
                'fixed_width': None
            },
            {
                'fixed_height': None,
                'fixed_width': 10
            },
            {'fixed_scale': 2}

        ]
        for data in true_values:
            assert ProcessConf.set_output_size(data) == data

        assert ProcessConf.set_output_size({'fixed_size': 260}) == {
            'fixed_height': 260,
            'fixed_width': 260
        }

    @staticmethod
    def test_is_output_write_jpg_format():
        """Test is_output_write_jpg_format method"""
        true_values = [
            {'ext': '.jpg'},
            {'ext': '.jpeg', 'quality': 100},
            {'ext': '.jPg', 'quality': 50, 'progressive': 0},
            {'ext': '.jPeg', 'quality': 50, 'progressive': 1, 'optimize': 1},
            {'ext': '.jPeg', 'quality': 50, 'progressive': 1, 'optimize': 0}
        ]
        for data in true_values:
            assert ProcessConf.is_output_write_jpg_format(data) is True

        false_values = [
            {'ext': '.png'},
            {'ext': '.jpeg', 'quality': 101},
            {'ext': '.jpeg', 'quality': -1},
            {'ext': '.jPg', 'quality': 50, 'progressive': 2},
            {'ext': '.jPg', 'quality': 50, 'progressive': -1},
            {'ext': '.jPeg', 'quality': 50, 'progressive': 1, 'optimize': 2},
            {'ext': '.jPeg', 'quality': 50, 'progressive': 1, 'optimize': -1}
        ]
        for data in false_values:
            assert ProcessConf.is_output_write_jpg_format(data) is False

    @staticmethod
    def test_is_output_write_webp_format():
        """Test is_output_write_webp_format method"""
        true_values = [
            {'ext': '.webp'},
            {'ext': '.webP', 'quality': 100},
            {'ext': '.wEbP', 'quality': 50},
            {'ext': '.Webp', 'quality': 0}
        ]
        for data in true_values:
            assert ProcessConf.is_output_write_webp_format(data) is True

        false_values = [
            {'ext': '.png'},
            {'ext': 'webp'},
            {'ext': '.webp', 'quality': 101},
            {'ext': '.webp', 'quality': -1}
        ]
        for data in false_values:
            assert ProcessConf.is_output_write_webp_format(data) is False

    @staticmethod
    def test_is_output_write_png_format():
        """Test is_output_write_png_format method"""
        true_values = [
            {'ext': '.png'},
            {'ext': '.pNg', 'compression': 0},
            {'ext': '.png', 'compression': 5},
            {'ext': '.png', 'compression': 9}
        ]
        for data in true_values:
            assert ProcessConf.is_output_write_png_format(data) is True

        false_values = [
            {'ext': '.webp'},
            {'ext': 'png'},
            {'ext': '.png', 'compression': 10},
            {'ext': '.png', 'compression': -1}
        ]
        for data in false_values:
            assert ProcessConf.is_output_write_png_format(data) is False

    @staticmethod
    def test_is_output_write_formats():
        """Test is_output_write_formats method"""
        true_values = [
            {'ext': '.png'},
            {'ext': '.pNg', 'compression': 0},
            {'ext': '.wEbP'},
            {'ext': '.wEbP', 'quality': 50},
            {'ext': '.jPeg'},
            {'ext': '.jPeg', 'quality': 50, 'progressive': 1, 'optimize': 1},
        ]
        for data in true_values:
            assert ProcessConf.is_output_write_formats(data) is True

        false_values = [
            {'nop': '.webp'},
            {'ext': 'png'},
            {'ext': '.tar'},
            {'ext': '.pdf'},
            {'ext': '.png', 'compression': 10},
            {'ext': '.webp', 'quality': 101},
            {'ext': '.jpeg', 'quality': 101},
        ]
        for data in false_values:
            assert ProcessConf.is_output_write_formats(data) is False

    @staticmethod
    def test_set_write_format():
        """Test set_write_format method"""
        true_values = [
            {'ext': '.png'},
            {'ext': '.pNg', 'compression': 0},
            {'ext': '.wEbP'},
            {'ext': '.wEbP', 'quality': 50},
            {'ext': '.jPeg'},
            {'ext': '.jPeg', 'quality': 50, 'progressive': 1, 'optimize': 1},
        ]
        assert ProcessConf.set_write_format(true_values) == {'formats': true_values}

        assert ProcessConf.set_write_format([]) is None

        error_values = [
            {'nop': '.webp'},
            {'ext': 'png'},
            {'ext': '.tar'},
            {'ext': '.pdf'},
            {'ext': '.png', 'compression': 10},
            {'ext': '.webp', 'quality': 101},
            {'ext': '.jpeg', 'quality': 101},
        ]

        with pytest.raises(SettingInvalidException):
            ProcessConf.set_write_format(error_values)
