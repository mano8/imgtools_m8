"""
ImageToolsHelper class.
"""
import os
import pathlib
import math
from numpy import ndarray
from ve_utils.utils import UType as Ut
from imgtools_m8.exceptions import ImgToolsException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class ImageToolsHelper:
    """
        ImageToolsHelper
    """

    @staticmethod
    def need_upscale(height: int,
                     width: int,
                     fixed_height: int or None = None,
                     fixed_width: int or None = None,
                     fixed_size: int or None = None
                     ) -> bool:
        """Test if image need upscale"""
        result = False
        if Ut.is_int(height, not_null=True) \
                and Ut.is_int(width, not_null=True):

            if Ut.is_int(fixed_width, not_null=True) \
                    and Ut.is_int(fixed_height, not_null=True) \
                    and fixed_width > width \
                    and fixed_height > height:
                result = True
            elif Ut.is_int(fixed_height, not_null=True) \
                    and fixed_height > height:
                result = True
            elif Ut.is_int(fixed_width, not_null=True) \
                    and fixed_width > width:
                result = True
            elif Ut.is_int(fixed_size, not_null=True) \
                    and fixed_size > width \
                    and fixed_size > height:
                result = True
        else:
            raise ImgToolsException(
                "Error: Bad image size values."
            )
        return result

    @staticmethod
    def get_model_scale_needed(height: int,
                               width: int,
                               fixed_height: int or None = None,
                               fixed_width: int or None = None,
                               fixed_size: int or None = None
                               ) -> int:
        """
        Get model scale to load
        """
        result = 0
        if height > 0 and width > 0:
            if Ut.is_int(fixed_height, not_null=True) \
                    and Ut.is_int(fixed_width, not_null=True) \
                    and fixed_height > height \
                    and fixed_width > width:
                scale_w = math.ceil(fixed_width / width)
                scale_h = math.ceil(fixed_height / height)
                result = min(scale_w, scale_h)

            elif Ut.is_int(fixed_width, not_null=True) \
                    and fixed_width > width:
                result = math.ceil(fixed_width / width)

            elif Ut.is_int(fixed_height, not_null=True) \
                    and fixed_height > height:
                result = math.ceil(fixed_height / height)

            elif Ut.is_int(fixed_size, not_null=True) \
                    and fixed_size > width \
                    and fixed_size > height:
                scale_w = math.ceil(fixed_size / width)
                scale_h = math.ceil(fixed_size / height)
                result = min(scale_w, scale_h)

        return result

    @staticmethod
    def count_upscale(height: int,
                      width: int,
                      model_scale: int,
                      fixed_height: int or None = None,
                      fixed_width: int or None = None,
                      fixed_size: int or None = None
                      ) -> int:
        """
        Count nb max of upscale needed
        """
        result = 0
        if model_scale > 0 \
                and height > 0 \
                and width > 0:
            while ImageToolsHelper.need_upscale(
                    width=width,
                    height=height,
                    fixed_width=fixed_width,
                    fixed_height=fixed_height,
                    fixed_size=fixed_size):
                width = width * model_scale
                height = height * model_scale
                result += 1
        return result

    @staticmethod
    def get_upscale_stats(size: tuple,
                          output_formats: list,
                          model_scale: int
                          ) -> dict:
        """
        Get upscale stats from output configuration sizes
        """
        counter, result = 0, None
        h, w = size
        if Ut.is_list(output_formats, not_null=True)\
                and Ut.is_int(model_scale, not_null=True):
            result = {
                'max_upscale': 0,
                'stats': []
            }
            for key, output_format in enumerate(output_formats):

                fixed_height = output_format.get('fixed_height')
                fixed_width = output_format.get('fixed_width')
                fixed_size = output_format.get('fixed_size')
                tmp = ImageToolsHelper.count_upscale(
                        width=w,
                        height=h,
                        model_scale=model_scale,
                        fixed_width=fixed_width,
                        fixed_height=fixed_height,
                        fixed_size=fixed_size)
                x_scale = ImageToolsHelper.get_model_scale_needed(
                        width=w,
                        height=h,
                        fixed_width=fixed_width,
                        fixed_height=fixed_height,
                        fixed_size=fixed_size)
                counter = max(counter, tmp)
                result['stats'].append({
                    'key': key,
                    'nb_upscale': tmp,
                    'x_scale': x_scale
                })
            result['stats'] = sorted(
                result.get('stats'),
                key=lambda d: d['nb_upscale']
            )
            result['max_upscale'] = counter
        return result

    @staticmethod
    def get_image_size(image: ndarray) -> tuple or None:
        """Get image size tuple (h, w)"""
        size = None
        if image is not None:
            size = image.shape[:2]
        return size

    @staticmethod
    def get_package_models_path() -> str or None:
        """Get package models' path."""
        return os.path.join(os.path.dirname(__file__), 'models')

    @staticmethod
    def get_images_list(path):
        """List images from path."""
        return ImageToolsHelper.get_files_list(path, ext=ImageToolsHelper.get_valid_images_ext())

    @staticmethod
    def get_files_list(path: str,
                       ext: str or list or None = None,
                       content_name: str or None = None
                       ) -> list or None:
        """
        List files from path.
        Can extract files names by:
          - extension(s)
          - file name content
        """
        result = None
        if Ut.is_str(path, not_null=True) \
                and os.path.isdir(path):
            result = [
                f
                for f in os.listdir(path)
                if os.path.isfile(os.path.join(path, f))
                and (ext is None
                     or (Ut.is_list(ext, not_null=True) and ImageToolsHelper.get_extension(f) in ext)
                     or (Ut.is_str(ext, not_null=True) and ImageToolsHelper.get_extension(f) == ext)
                     )
                and (content_name is None
                     or (Ut.is_str(content_name, not_null=True) and content_name in f)
                     )
            ]
        return result

    @staticmethod
    def get_valid_images_ext():
        """Get valid images extensions"""
        return [
            '.bmp', '.dib',
            '.jpg', '.jpeg', '.jpe',
            '.jp2', '.png', '.webp',
            '.avif', '.pbm', '.pgm',
            '.ppm', '.pxm', '.pnm',
            '.pfm', '.sr', '.ras',
            '.tiff', '.tif', '.exr',
            '.hdr', '.pic'
        ]

    @staticmethod
    def get_valid_jpg_ext():
        """Get valid images extensions"""
        return [
            '.jpg', '.jpeg', '.jpe', '.jp2'
        ]

    @staticmethod
    def is_valid_image_ext(ext: str) -> bool:
        """List directory files"""
        result = False
        if Ut.is_str(ext, not_null=True):
            ext = ext.lower()
            result = ext in ImageToolsHelper.get_valid_images_ext()
        return result

    @staticmethod
    def is_valid_jpg_ext(ext: str):
        """List directory files"""
        ext = ext.lower()
        return ext in ImageToolsHelper.get_valid_jpg_ext()

    @staticmethod
    def cut_file_name(file_name: str, ext_len: int = 1) -> tuple:
        """Set image output path file"""
        name = None
        ext = ImageToolsHelper.get_extension(file_name, ext_len)
        if Ut.is_str(file_name, not_null=True) \
                and Ut.is_str(ext):
            name = file_name.replace(ext, '')
        return name, ext

    @staticmethod
    def get_extension(path: str, ext_len: int = 1) -> str:
        """Get extension from file path."""
        ext = None
        if Ut.is_str(path, not_null=True):
            ext_len = Ut.get_int(ext_len, default=1)
            if ext_len == 1:
                ext = pathlib.Path(path).suffix
            elif ext_len == 2:
                ext_list = pathlib.Path(path).suffixes[-2:]
                ext = "".join(ext_list)
            elif ext_len == 3:
                ext_list = pathlib.Path(path).suffixes[-3:]
                ext = "".join(ext_list)
            else:
                ext = "".join(pathlib.Path(path).suffixes)
            ext = ext.lower()
        return ext

    @staticmethod
    def convert_size(size_bytes):
        """Convert bytes to more reliable size unit"""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return "%s %s" % (s, size_name[i])

    @staticmethod
    def get_string_file_size(source_path: str) -> str:
        """Get file size from path"""
        result = ""
        if os.path.isfile(source_path):
            result = ImageToolsHelper.convert_size(
                os.path.getsize(source_path)
            )
        return result
