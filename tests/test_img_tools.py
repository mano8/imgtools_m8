"""
ImageTools unittest class.

Use pytest package.
"""
import pytest
import os
from numpy import ndarray
from imgtools_m8.img_tools import ImageTools
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.exceptions import ImgToolsException
from imgtools_m8.exceptions import SettingInvalidException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestImageTools:

    def setup_method(self):
        """
        Setup any state tied to the execution of the given function.

        Invoked for every test function in the module.
        """
        model_conf = {
            'path': os.path.join(os.path.abspath('..'), 'models'),
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsr',
            'scale': 2
        }
        source_path = os.path.join(os.path.abspath('.'), 'dummy_dir')
        output_conf = {
            'path': os.path.join(os.path.abspath('.'), 'dummy_output'),
            'output_formats': [
                {
                    'fixed_width': 450,
                    'fixed_height': 450,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 80}
                    ]
                }
            ]

        }

        self.obj = ImageTools(
            model_conf=model_conf,
            source_path=source_path,
            output_conf=output_conf
        )

    def test_has_conf(self):
        """Test has_conf method"""
        assert self.obj.has_conf() is True

    def test_set_output_conf(self):
        """Test set_output_conf method"""
        output_conf = {
            'path': os.path.join(os.path.abspath('.'), 'dummy_output'),
            'output_formats': [
                {
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 80}
                    ]
                }
            ]
        }
        assert self.obj.set_output_conf(output_conf) is True
        # test bad formats values
        output_conf['output_formats'][0]['formats'] = [{'bad': 0}]
        with pytest.raises(SettingInvalidException):
            self.obj.set_output_conf(output_conf)

        # test bad formats values
        output_conf['output_formats'][0]['formats'] = None
        with pytest.raises(SettingInvalidException):
            self.obj.set_output_conf(output_conf)

        # test bad output_formats
        output_conf['output_formats'] = None
        with pytest.raises(SettingInvalidException):
            self.obj.set_output_conf(output_conf)
        # test bad output_conf
        output_conf = {}
        with pytest.raises(SettingInvalidException):
            self.obj.set_output_conf(output_conf)

    def test_run(self):
        """Test run method"""
        # test: Resize all images in dummy_dir
        # upscale 2x then downscale to height size of 450px
        tst = self.obj.run()
        assert tst is True

    def test_run_1900w(self):
        """Test run method"""
        # test: Resize specific image in dummy_dir
        # upscale 6x then downscale to width size of 1900px
        self.obj.set_source_path(
            source_path=os.path.join(os.path.abspath('.'), 'dummy_dir', 'recien_llegado.jpg')
        )
        output_conf = self.obj.output_conf
        output_conf.update({
            'output_formats': [
                {
                    'fixed_width': 1900,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 80}
                    ]
                },
                {
                    'fixed_width': 1200,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80, 'progressive': 1, 'optimize': 1},
                        {'ext': '.png', 'compression': 2}
                    ]
                },
                {
                    'fixed_height': 381,
                    'formats': [
                        {'ext': '.jpg'}
                    ]
                },
                {
                    'fixed_size': 200,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80}
                    ]
                }
            ]
        })
        self.obj.set_output_conf(output_conf)
        tst = self.obj.run()
        assert tst is True

    def test_run_only_quality(self):
        """Test run method"""
        # test: Resize specific image in dummy_dir
        # 50% jpg quality
        self.obj.set_source_path(
            source_path=os.path.join(os.path.abspath('.'), 'dummy_dir', 'mar.jpg')
        )
        output_conf = self.obj.output_conf
        output_conf.update({
            'output_formats': [
                {
                    'formats': [
                        {'ext': '.webp', 'quality': 80}
                    ]
                },
                {
                    'fixed_width': 250,
                    'fixed_height': 300,
                    'formats': [
                        {'ext': '.webp', 'quality': 80}
                    ]
                },
                {
                    'fixed_size': 100,
                    'formats': [
                        {'ext': '.webp', 'quality': 80}
                    ]
                }
            ]
        })
        self.obj.set_output_conf(output_conf)
        tst = self.obj.run()
        assert tst is True

    @staticmethod
    def test_is_source_path():
        """Test is_source_path method."""
        assert ImageTools.is_source_path(
            source_path=os.path.join(os.path.abspath('.'), 'dummy_dir')
        ) is True
        assert ImageTools.is_source_path(
            source_path=os.path.join(os.path.abspath('.'), 'dummy_dir', 'recien_llegado.jpg')
        ) is True
        assert ImageTools.is_source_path(
            source_path=os.path.join(os.path.abspath('.'), 'dummy_dir', 'bad_file')
        ) is False
        assert ImageTools.is_source_path(
            source_path=os.path.join(os.path.abspath('.'), 'bad_dir')
        ) is False

    @staticmethod
    def test_is_output_conf():
        """Test is_output_conf method"""

    @staticmethod
    def test_read_image():
        """Test read_image method"""
        image = ImageTools.read_image(os.path.join('dummy_dir', 'recien_llegado.jpg'))
        assert type(image) == ndarray
        assert image.shape[:2] == (216, 340)

    @staticmethod
    def test_get_image_size():
        """Test get_image_size method"""
        image = ImageTools.read_image(os.path.join('dummy_dir', 'recien_llegado.jpg'))
        size = ImageToolsHelper.get_image_size(image)
        assert size == (216, 340)

    @staticmethod
    def test_get_jpeg_write_options():
        """Test get_jpeg_write_options method"""
        assert ImageTools.get_jpeg_write_options({}) is None

    @staticmethod
    def test_get_webp_write_options():
        """Test get_webp_write_options method"""
        assert ImageTools.get_webp_write_options({}) is None

    @staticmethod
    def test_get_png_write_options():
        """Test get_png_write_options method"""
        assert ImageTools.get_png_write_options({}) is None

    @staticmethod
    def test_image_resize():
        """Test image_resize method"""
        image = ImageTools.read_image(os.path.join('dummy_dir', 'recien_llegado.jpg'))
        resized = ImageTools.image_resize(image, width=200)
        assert image.shape[:2] == (216, 340)
        assert resized.shape[:2] == (127, 200)
        resized = ImageTools.image_resize(image, height=200)
        assert resized.shape[:2] == (200, 314)
        resized = ImageTools.image_resize(image)
        assert resized.shape[:2] == (216, 340)
        with pytest.raises(ImgToolsException):
            ImageTools.image_resize(
                image=resized,
                width=0,
                height=0
            )