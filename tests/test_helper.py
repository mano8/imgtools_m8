"""
ImageToolsHelper unittest class.

Use pytest package.
"""
import os
import cv2
import pytest
from .helper import HelperTest
from ve_utils.utils import UType as Ut
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.exceptions import ImgToolsException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestImageToolsHelper:

    @staticmethod
    def test_need_upscale():
        """Test need_upscale method"""
        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_width=22
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_width=18
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_width=25
        ) is True

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_height=22
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_height=18
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_width=25,
            fixed_height=25
        ) is True

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_height=25
        ) is True

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_size=22
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_size=18
        ) is False

        assert ImageToolsHelper.need_upscale(
            width=22,
            height=22,
            fixed_size=25
        ) is True

        with pytest.raises(ImgToolsException):
            ImageToolsHelper.need_upscale(
                width=0,
                height=22
            )

        with pytest.raises(ImgToolsException):
            ImageToolsHelper.need_upscale(
                width=22,
                height=0
            )

    @staticmethod
    def test_get_model_scale_needed():
        """Test get_model_scale_needed method"""
        height, width = (200, 400)
        output_formats = [
            {'height': 200, 'width': 400, 'fixed_width': 1900},
            {'height': 200, 'width': 500, 'fixed_width': 1600, 'fixed_height': 1600},
            {'height': 200, 'width': 300, 'fixed_width': 1200, 'fixed_height': 800},
            {'height': 200, 'width': 400, 'fixed_size': 900},
            {'height': 200, 'width': 500, 'fixed_height': 600},
            {'height': 200, 'width': 400, 'fixed_width': 200}
        ]
        results = []
        for params in output_formats:
            scale = ImageToolsHelper.get_model_scale_needed(**params)
            results.append(scale)
        assert results == [5, 4, 4, 3, 3, 0]

    @staticmethod
    def test_get_upscale_stats():
        """Test get_upscale_stats method"""
        size = (200, 400)
        output_formats = [
            {'fixed_width': 1900},
            {'fixed_width': 1600},
            {'fixed_width': 1200},
            {'fixed_width': 900},
            {'fixed_width': 600},
            {'fixed_width': 200}
        ]
        stats = ImageToolsHelper.get_upscale_stats(
            size=size,
            output_formats=output_formats,
            model_scale=2
        )
        assert stats.get('max_upscale') == 3
        assert len(stats.get('stats')) == len(output_formats)
        output_formats = [
            {'fixed_width': 350},
            {'fixed_width': 200},
            {'fixed_height': 150},
            {'fixed_size': 100}
        ]
        stats = ImageToolsHelper.get_upscale_stats(
            size=size,
            output_formats=output_formats,
            model_scale=2
        )
        assert stats.get('max_upscale') == 0
        assert len(stats.get('stats')) == len(output_formats)

    @staticmethod
    def test_get_images_list():
        """Test get_images_list method"""
        files = ImageToolsHelper.get_images_list(
            HelperTest.get_source_path()
        )
        assert len(files) == 3

    @staticmethod
    def test_get_files_list():
        """Test get_files_list method"""
        sources = HelperTest.get_source_path()
        files = ImageToolsHelper.get_files_list(sources)
        assert len(files) == 5
        files = ImageToolsHelper.get_files_list(sources, ext='.jpg')
        assert len(files) == 3
        files = ImageToolsHelper.get_files_list(sources, ext=['.jpg', '.txt'])
        assert len(files) == 5
        files = ImageToolsHelper.get_files_list(sources, ext='.jpg', content_name="bad_")
        assert len(files) == 1 and files[0] == "bad_image.jpg"

    @staticmethod
    def test_is_valid_image_ext():
        """Test is_valid_image_ext method"""
        assert not ImageToolsHelper.is_valid_image_ext(ext='EDSR_x2.pb')
        assert not ImageToolsHelper.is_valid_image_ext(ext='.pb')
        assert ImageToolsHelper.is_valid_image_ext(ext='.jpeg')
        assert ImageToolsHelper.is_valid_image_ext(ext='.jPeG')
        assert ImageToolsHelper.is_valid_image_ext(ext='.jPG')
        assert ImageToolsHelper.is_valid_image_ext(ext='.png')

    @staticmethod
    def test_is_valid_jpg_ext():
        """Test is_valid_jpg_ext method"""
        assert ImageToolsHelper.is_valid_jpg_ext('.JpEg') is True

    @staticmethod
    def test_cut_file_name():
        """Test cut_file_name method"""
        assert ImageToolsHelper.cut_file_name(file_name='EDSR_x2.pb') == ('EDSR_x2', '.pb')
        assert ImageToolsHelper.cut_file_name(file_name='img.jpg') == ('img', '.jpg')
        assert ImageToolsHelper.cut_file_name(file_name='img') == ('img', '')
        assert ImageToolsHelper.cut_file_name(file_name='img.tar.gz') == ('img.tar', '.gz')
        assert ImageToolsHelper.cut_file_name(file_name='img.back.tar.gz', ext_len=2) == ('img.back', '.tar.gz')
        assert ImageToolsHelper.cut_file_name(file_name='img.back.tar.gz', ext_len=0) == ('img', '.back.tar.gz')

    @staticmethod
    def test_get_extension():
        """Test get_extension method"""
        assert ImageToolsHelper.get_extension(path='EDSR_x2.pb') == '.pb'
        assert ImageToolsHelper.get_extension(path='EDSR_x2.Pb') == '.pb'
        assert ImageToolsHelper.get_extension(path='img.jpg') == '.jpg'
        assert ImageToolsHelper.get_extension(path='img') == ''
        assert ImageToolsHelper.get_extension(path='img.tar.gz') == '.gz'
        assert ImageToolsHelper.get_extension(path='img.back.tar.gz', ext_len=2) == '.tar.gz'
        assert ImageToolsHelper.get_extension(path='img.tar.gz.sav', ext_len=3) == '.tar.gz.sav'
        assert ImageToolsHelper.get_extension(path='img.tAr.gZ.sAv', ext_len=3) == '.tar.gz.sav'
        assert ImageToolsHelper.get_extension(path='img.tar.gz', ext_len=3) == '.tar.gz'

    @staticmethod
    def test_get_image_size():
        """Test get_image_size method"""
        image = cv2.imread(
            os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado.jpg')
        )
        assert ImageToolsHelper.get_image_size(
            image
        ) == (216, 340)

    @staticmethod
    def test_get_package_models_path():
        """Test get_package_models_path method"""
        path = ImageToolsHelper.get_package_models_path()
        assert Ut.is_str(path) and "models" in path

    @staticmethod
    def test_convert_size():
        """Test convert_size method"""
        assert ImageToolsHelper.convert_size(0) == "0 B"
        assert ImageToolsHelper.convert_size(100) == "100.0 B"
        assert ImageToolsHelper.convert_size(10000) == "9.77 KB"
        assert ImageToolsHelper.convert_size(10000000) == "9.54 MB"

    @staticmethod
    def test_get_string_file_size():
        """Test get_string_file_size method"""
        assert ImageToolsHelper.get_string_file_size(
            os.path.join(
                HelperTest.get_source_path(),
                'recien_llegado.jpg')
        ) == "77.52 KB"
