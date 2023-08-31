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
from imgtools_m8.model_scale_selector import ModelScaleSelector
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
                    'fixed_width': 35,
                    'fixed_height': 22,
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

    def test_set_expander(self):
        """Test set_expander method"""
        assert self.obj.set_expander(model_conf=None) is False
        assert self.obj.set_expander(model_conf={'scale': 2}) is True

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

    def test_change_scale_strategy(self):
        """Test some methods to update and get model scale strategy"""
        # fixed scale
        assert self.obj.set_fixed_scale(3) is True
        assert self.obj.get_model_scale() == 3
        assert self.obj.is_auto_scale() is False
        with pytest.raises(ImgToolsException):
            self.obj.set_fixed_scale(-1)
        # auto scale
        assert self.obj.set_auto_scale() is True
        assert self.obj.get_model_scale() == 2
        assert self.obj.is_auto_scale() is True

    def test_upscale_with_auto_scale(self):
        """Test upscale_with_auto_scale method"""
        image = self.obj.read_image(
            os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado_min.jpg'
            )
        )
        size = ImageToolsHelper.get_image_size(image)
        upscale_stats = ModelScaleSelector.get_upscale_stats(
            size=size,
            output_formats=self.obj.conf.get_output_formats(),
            model_scale=self.obj.get_model_scale()
        )
        upscale_stats = ModelScaleSelector.define_model_scale(
            upscale_stats=upscale_stats,
            available_scales=self.obj.get_available_model_scales()
        )
        output_formats = [
            {
                'fixed_width': 80,
                'formats': [
                    {'ext': '.jpeg'}
                ]
            }
        ]
        self.obj.set_output_formats(output_formats)
        assert self.obj.upscale_with_auto_scale(
            image=image,
            upscale_stats=upscale_stats,
            file_name=''
        ) is False


    def test_upscale_with_fixed_scale(self):
        """Test upscale_with_fixed_scale method"""
        image = self.obj.read_image(
            os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado_min.jpg'
            )
        )
        size = ImageToolsHelper.get_image_size(image)
        output_formats = [
            {
                'fixed_width': 80,
                'formats': [
                    {'ext': '.jpeg'}
                ]
            }
        ]
        self.obj.set_output_formats(output_formats)
        upscale_stats = ModelScaleSelector.get_upscale_stats(
            size=size,
            output_formats=self.obj.conf.get_output_formats(),
            model_scale=self.obj.get_model_scale()
        )

        assert self.obj.upscale_with_fixed_scale(
            image=image,
            upscale_stats=upscale_stats,
            file_name=''
        ) is False

        output_formats = [
            {
                'fixed_width': 35,
                'formats': [
                    {'ext': '.jpeg'}
                ]
            }
        ]
        self.obj.set_output_formats(output_formats)
        upscale_stats = ModelScaleSelector.get_upscale_stats(
            size=size,
            output_formats=self.obj.conf.get_output_formats(),
            model_scale=self.obj.get_model_scale()
        )
        assert self.obj.upscale_with_fixed_scale(
            image=image,
            upscale_stats=upscale_stats,
            file_name=os.path.basename(self.obj.conf.get_source_path())
        ) is True

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

    def test_fixed_scale(self):
        """Test run method"""
        self.obj.set_fixed_scale(2)
        self.obj.set_source_path(
            source_path=os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado_min.jpg')
        )
        output_formats = [
            {
                'fixed_width': 80,
                'formats': [
                    {'ext': '.webp', 'quality': 80}
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
    def test_get_downscale_size():
        """Test get_downscale_size method"""

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
        assert ImageTools.get_downscale_size(
            size=(216, 340),
            fixed_height=200,
            fixed_width=300
        ) == {'width': 300}

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
            output_formats=[
                {'ext_bad': '.webp', 'quality_bad': 80}
            ]
        ) is False

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
