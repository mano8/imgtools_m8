"""
ImageTools unittest class.

Use pytest package.
"""
import pytest
import os
from .helper import HelperTest
from imgtools_m8.process_conf import ProcessConf
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
        output_formats = [
                {
                    'fixed_width': 260,
                    'fixed_height': 200,
                    'formats': [
                        {'ext': '.jpg', 'quality': 80}
                    ]
                }
            ]

        self.obj = ImageTools(
            source_path=HelperTest.get_source_path(),
            output_path=HelperTest.get_output_path(),
            output_formats=output_formats
        )

    def test_has_conf(self):
        """Test has_conf method"""
        assert self.obj.has_conf() is True

    def test_set_conf(self):
        """Test set_conf method"""
        conf = {
            'source_path': HelperTest.get_source_path(),
            'output_path': HelperTest.get_output_path(),
            'output_formats': [
                {
                    'formats': [
                        {'ext': '.jpg', 'quality': 80},
                        {'ext': '.webp', 'quality': 80}
                    ]
                }
            ]
        }
        assert self.obj.set_conf(**conf) is True
        # test bad formats values
        conf['output_formats'][0]['formats'] = [{'bad': 0}]
        with pytest.raises(SettingInvalidException):
            self.obj.set_conf(**conf)

        # test bad formats values
        conf['output_formats'][0]['formats'] = None
        with pytest.raises(SettingInvalidException):
            self.obj.set_conf(**conf)

        # test bad output_formats
        conf['output_formats'] = None
        with pytest.raises(SettingInvalidException):
            self.obj.set_conf(**conf)

        assert self.obj.set_output_path(HelperTest.get_output_path()) is True

    def test_get_available_model_scales(self):
        """Test get_available_model_scales method"""
        assert self.obj.get_available_model_scales() == [2, 3, 4]

    def test_run(self):
        """Test run method"""
        tst = self.obj.run()
        # unable to upscale bad_image.jpg
        assert tst is False
        self.obj.set_source_path(
            source_path=os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado.jpg')
        )
        output_formats = [
            {
                'fixed_height': 381,
                'formats': [
                    {'ext': '.jpg'}
                ]
            },
            {
                'fixed_width': 220,
                'formats': [
                    {'ext': '.png', 'compression': 3}
                ]
            },
            {
                'fixed_size': 200,
                'formats': [
                    {'ext': '.jpg', 'quality': 80, 'progressive': 1, 'optimize': 1}
                ]
            }
        ]
        self.obj.set_output_formats(output_formats)
        tst = self.obj.run()
        assert tst is True

    def test_run_only_quality(self):
        """Test run method"""
        # test: Resize specific image in sources_test
        # 50% jpg quality

        self.obj.set_source_path(
            source_path=os.path.join(
                HelperTest.get_source_path(),
                'mar.jpg')
        )
        output_formats = [
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
        self.obj.set_output_formats(output_formats)
        tst = self.obj.run()
        assert tst is True

    @staticmethod
    def test_is_resize_need():
        """Test resize_need method"""

        assert ImageTools.get_downscale_size(
            size=(139, 200),
            fixed_height=140,
            fixed_width=180
        ) == {'width': 180}

        assert ImageTools.get_downscale_size(
            size=(139, 200),
            fixed_height=138,
            fixed_width=180
        ) == {'width': 180}
        assert ImageTools.get_downscale_size(
            size=(139, 200),
            fixed_height=100,
            fixed_width=180
        ) == {'height': 100}
        assert ImageTools.get_downscale_size(
            size=(139, 200),
            fixed_height=100,
            fixed_width=100
        ) == {'width': 100}

    @staticmethod
    def test_is_source_path():
        """Test is_source_path method."""
        assert ProcessConf.is_source_path(
            source_path=HelperTest.get_source_path()
        ) is True
        assert ProcessConf.is_source_path(
            source_path=os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado.jpg')
        ) is True
        assert ProcessConf.is_source_path(
            source_path=os.path.join(
                HelperTest.get_source_path(),
                'bad_file')
        ) is False
        assert ProcessConf.is_source_path(
            source_path=os.path.join(
                HelperTest.get_source_path(),
                'bad_dir')
        ) is False

    @staticmethod
    def test_write_images_by_format():
        """Test write_images_by_format method"""
        source_path = os.path.join(
            HelperTest.get_source_path(),
            'mar.jpg')
        image = ImageTools.read_image(source_path)
        assert ImageTools.write_images_by_format(
            image=image,
            output_path=HelperTest.get_output_path(),
            file_name="bad",
            output_format=[
                {'ext_bad': '.webp', 'quality_bad': 80}
            ]
        ) is False

    @staticmethod
    def test_write_image():
        """Test write_image method"""
        with pytest.raises(ImgToolsException):
            ImageTools.write_image(
                image=None,
                output_path="bad",
                file_name="bad",
                ext=".jpeg"
            )

    @staticmethod
    def test_read_image():
        """Test read_image method"""
        image = ImageTools.read_image(os.path.join(
            HelperTest.get_source_path(),
            'recien_llegado.jpg'))
        assert image is not None
        assert image.shape[:2] == (216, 340)

    @staticmethod
    def test_get_image_size():
        """Test get_image_size method"""
        image = ImageTools.read_image(os.path.join(
            HelperTest.get_source_path(),
            'recien_llegado.jpg'))
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
        image = ImageTools.read_image(os.path.join(
            HelperTest.get_source_path(),
            'recien_llegado.jpg'))
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
