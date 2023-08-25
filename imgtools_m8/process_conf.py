"""Process Configuration class"""
import logging
from os import path as Path
from ve_utils.utils import UType as Ut
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.exceptions import ImgToolsException
from imgtools_m8.exceptions import SettingInvalidException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"

logging.basicConfig()
logger = logging.getLogger("imgTools_m8")


class ProcessConf:
    """
    Process configuration parameters.

    :param source_path: The path to the source directory containing images.
    :type source_path: str, optional
    :param output_formats: A list of output image formats to be used for saving.
    :type output_formats: list, optional
    :param output_path: The path to the output directory where processed images will be saved.
    :type output_path: str, optional
    """

    def __init__(self,
                 source_path: str,
                 output_formats: list,
                 output_path: str,
                 ):
        """
        Initialize the ProcessConf instance.

        :param source_path: The path to the source directory containing images.
        :type source_path: str
        :param output_formats: A list of output image formats to be used for saving.
        :type output_formats: list
        :param output_path: The path to the output directory where processed images will be saved.
        :type output_path: str
        """
        self.source_path = None
        self.output_formats = None
        self.output_path = None
        self.set_source_path(source_path)
        self.set_output_formats(output_formats)
        self.set_output_path(output_path)

    def is_ready(self) -> bool:
        """
        Check if the ProcessConf instance is ready for image processing.

        :return: True if the instance is ready, False otherwise.
        :rtype: bool

        Example:
            >>> config = ProcessConf(
            >>> source_path='path/to/source', output_formats=['jpg', 'png'], output_path='path/to/output'
            >>> )
            >>> config.is_ready()
            True
        """
        return self.has_source_path() \
            and self.has_output_formats() \
            and self.has_output_path()

    def has_source_path(self) -> bool:
        """
        Check if the instance has a valid source path.

        :return: True if the source path is valid, False otherwise.
        :rtype: bool

        Example:
            >>> config = ProcessConf(source_path="/path/to/images", output_formats=["jpg", "png"])
            >>> config.has_source_path()
            True
        """
        return ProcessConf.is_source_path(self.source_path)

    def set_source_path(self, value: str) -> bool:
        """
        Set the source path for image processing.

        :param value: The path to the source directory or image file.
        :type value: str

        :return: True if the source path was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> config = ProcessConf(output_formats=["jpg", "png"])
            >>> config.set_source_path("/path/to/images")
            True
        """
        result = False
        self.source_path = None
        if ProcessConf.is_source_path(value):
            self.source_path = value
            result = True
        return result

    def get_source_path(self) -> str:
        """
        Get the source path for image processing.

        :return: The source path.
        :rtype: str

        Example:
            >>> config = ProcessConf(source_path="/path/to/images", output_formats=["jpg", "png"])
            >>> config.get_source_path()
            '/path/to/images'
        """
        return self.source_path

    def has_output_formats(self) -> bool:
        """
        Check if the instance has valid output formats.

        :return: True if the output formats are valid, False otherwise.
        :rtype: bool

        Example:
            >>> config = ProcessConf(source_path="/path/to/images", output_formats=["jpg", "png"])
            >>> config.has_output_formats()
            True
        """

        return ProcessConf.is_output_formats(self.output_formats)

    def set_output_formats(self, data: list) -> bool:
        """
        Set the output formats and configuration.

        :param data: A list of dictionaries containing output format configurations.
        :type data: list

        :return: True if the output formats were set successfully, False otherwise.
        :rtype: bool

        :raises SettingInvalidException: If the provided data contains invalid configuration.

        Example:
            >>> config = ProcessConf(source_path="/path/to/images")
            >>> output_formats = [{"formats": "jpg", "output_size": (800, 600)}, {"formats": "png"}]
            >>> config.set_output_formats(output_formats)
            True
        """
        self.output_formats = None
        if ProcessConf.is_output_formats(data):
            self.output_formats = []
            for output_format in data:
                conf = ProcessConf.set_output_format(output_format.get('formats'))
                if Ut.is_dict(conf):
                    conf.update(ProcessConf.set_output_size(output_format))
                else:
                    raise SettingInvalidException(
                        "[ImageTools::set_output_conf] "
                        "Error: Invalid output format configuration. %s",
                        output_format
                    )
                self.output_formats.append(conf)
            self.output_formats = data
            result = True
        else:
            raise SettingInvalidException(
                "[ImageTools::set_output_conf] "
                "Error: Invalid output formats configuration [{}]. %s ",
                data
            )
        return result

    def get_output_formats(self) -> str:
        """
        Get the list of output format configurations.

        :return: A list of dictionaries containing output format configurations.
        :rtype: list

        Example:
            >>> config = ProcessConf(source_path="/path/to/images")
            >>> output_formats = [{"formats": "jpg", "output_size": (800, 600)}, {"formats": "png"}]
            >>> config.set_output_formats(output_formats)
            >>> config.get_output_formats()
            [{'formats': 'jpg', 'output_size': (800, 600)}, {'formats': 'png'}]
        """
        return self.output_formats

    def has_output_path(self) -> bool:
        """
        Check if the instance has a valid output path.

        :return: True if the output path is valid, False otherwise.
        :rtype: bool

        Example:
            >>> config = ProcessConf(source_path="/path/to/images", output_formats=["jpg", "png"])
            >>> config.set_output_path("/path/to/output")
            >>> config.has_output_path()
            True
        """
        return ProcessConf.is_output_path(self.output_path)

    def set_output_path(self, value: str) -> bool:
        """
        Set the output path.

        :param value: The path to the output directory.
        :type value: str

        :return: True if the output path was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> config = ProcessConf(source_path="/path/to/images", output_formats=["jpg", "png"])
            >>> config.set_output_path("/path/to/output")
            True
        """
        result = False
        self.output_path = None
        if ProcessConf.is_output_path(value):
            self.output_path = value
            result = True
        return result

    def get_output_path(self) -> str:
        """
        Get the output path.

        :return: The output path.
        :rtype: str

        Example:
            >>> config = ProcessConf(source_path="/path/to/images", output_formats=["jpg", "png"])
            >>> config.set_output_path("/path/to/output")
            >>> config.get_output_path()
            '/path/to/output'
        """
        return self.output_path

    @staticmethod
    def is_source_path(source_path: str) -> bool:
        """
        Check if a given source path is valid.

        :param source_path: The source path to check.
        :type source_path: str

        :return: True if the source path is valid, False otherwise.
        :rtype: bool

        Example:
            >>> ProcessConf.is_source_path("/path/to/images")
            True
        """
        return Ut.is_str(source_path, not_null=True) \
            and (Path.isdir(source_path)
                 or Path.isfile(source_path))

    @staticmethod
    def is_output_path(output_path: str) -> bool:
        """
        Check if a given output path is valid.

        :param output_path: The output path to check.
        :type output_path: str

        :return: True if the output path is valid, False otherwise.
        :rtype: bool

        Example:
            >>> ProcessConf.is_output_path("/path/to/output")
            True
        """
        return Ut.is_str(output_path, not_null=True) \
            and Path.isdir(output_path)

    @staticmethod
    def is_output_formats(output_formats: list) -> bool:
        """
        Check if a list of output formats is valid.

        :param output_formats: A list of output formats to check.
        :type output_formats: list

        :return: True if the output formats list is valid, False otherwise.
        :rtype: bool

        Example:
            >>> ProcessConf.is_output_formats(["jpg", "png"])
            True
        """
        return Ut.is_list(output_formats, not_null=True)

    @staticmethod
    def is_fixed_width_or_height(data: dict) -> bool:
        """
        Check if a given output configuration contains valid fixed width or height settings.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains valid fixed width or height settings, False otherwise.
        :rtype: bool

        :raises SettingInvalidException: If the fixed_width or fixed_height values are invalid or mixed with other settings.

        Example:
            >>> config_data = {'fixed_width': 800, 'fixed_height': 600}
            >>> ProcessConf.is_fixed_width_or_height(config_data)
            True
        """
        is_not_fixed_width_or_height = data.get('fixed_height') is None \
            and data.get('fixed_width') is None

        is_fixed_width_or_height = (Ut.is_int(data.get('fixed_width'), mini=1)
                                    and Ut.is_int(data.get('fixed_height'), mini=1)) \
            or (Ut.is_int(data.get('fixed_width'), mini=1)
                and data.get('fixed_height') is None) \
            or (Ut.is_int(data.get('fixed_height'), mini=1)
                and data.get('fixed_width') is None)

        is_combined = data.get('fixed_size') is None \
            and data.get('fixed_scale') is None

        is_valid = is_fixed_width_or_height \
            and is_combined

        if not is_fixed_width_or_height\
                and not is_not_fixed_width_or_height:
            raise SettingInvalidException(
                "[ImageTools] Invalid output configuration: "
                "fixed_width and/or fixed_height value must be >= 1."
            )
        elif not is_valid\
                and not is_not_fixed_width_or_height:
            raise SettingInvalidException(
                "[ImageTools] Invalid output configuration: "
                "fixed_width and/or fixed_height can't be mixed with fixed_size and fixed_scale."
            )
        return not is_not_fixed_width_or_height

    @staticmethod
    def is_fixed_size(data: dict) -> bool:
        """
        Check if a given output configuration contains a valid fixed size setting.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains a valid fixed size setting, False otherwise.
        :rtype: bool

        :raises SettingInvalidException: If the fixed_size value is invalid or mixed with other settings.

        Example:
            >>> config_data = {'fixed_size': 800}
            >>> ProcessConf.is_fixed_size(config_data)
            True
        """
        is_not_fixed_size = data.get('fixed_size') is None

        is_fixed_size = Ut.is_int(data.get('fixed_size'), mini=1)

        is_combined = data.get('fixed_width') is None \
            and data.get('fixed_height') is None \
            and data.get('fixed_scale') is None

        is_valid = is_fixed_size \
            and is_combined

        if not is_fixed_size \
                and not is_not_fixed_size:
            raise SettingInvalidException(
                "[ImageTools] Invalid output configuration: "
                "fixed_size value must be >= 1."
            )
        elif not is_valid \
                and not is_not_fixed_size:
            raise SettingInvalidException(
                "[ImageTools] Invalid output configuration: "
                "fixed_size can't be mixed with an other option. "
                "(egg: fixed_width, fixed_height, fixed_scale)"
            )
        return not is_not_fixed_size

    @staticmethod
    def is_fixed_scale_value(data: dict) -> bool:
        """
        Check if a given output configuration contains a valid fixed scale setting.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains a valid fixed scale setting, False otherwise.
        :rtype: bool

        Example:
            >>> config_data = {'fixed_scale': 2}
            >>> ProcessConf.is_fixed_scale_value(config_data)
            True
        """
        return Ut.is_int(data.get('fixed_scale'), mini=2, maxi=10)

    @staticmethod
    def is_fixed_scale(data: dict) -> bool:
        """
        Check if a given output configuration contains a valid fixed scale setting.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains a valid fixed scale setting, False otherwise.
        :rtype: bool

        :raises SettingInvalidException:
            If the fixed scale value is not within the valid range.
            If fixed_scale is mixed with other options.

        Example:
            >>> output_format = {
            >>>     'fixed_scale': 2
            >>> }
            >>> ProcessConf.is_fixed_scale(output_format)
            >>> True
        """
        is_not_fixed_scale = data.get('fixed_scale') is None

        is_fixed_scale = ProcessConf.is_fixed_scale_value(data) \
            or data.get('fixed_scale') is None

        is_combined = data.get('fixed_width') is None \
            and data.get('fixed_height') is None \
            and data.get('fixed_size') is None

        is_valid = is_fixed_scale \
            and is_combined

        if not is_fixed_scale \
                and not is_not_fixed_scale:
            raise SettingInvalidException(
                "[ImageTools] Invalid output configuration: "
                "fixed_scale value must be >= 2 and <= 8."
            )
        elif not is_valid \
                and not is_not_fixed_scale:
            raise SettingInvalidException(
                "[ImageTools] Invalid output configuration: "
                "fixed_scale can't be mixed with an other option. "
                "(egg: fixed_width, fixed_height, fixed_size)"
            )
        return not is_not_fixed_scale

    @staticmethod
    def set_output_size(output_format: dict) -> dict:
        """
        Set the output size configuration based on the provided output format data.

        :param output_format: The output format data.
        :type output_format: dict

        :return: A dictionary containing the output size configuration.
        :rtype: dict

        Example:
            >>> output_format = {
            >>>     'fixed_scale': 2
            >>> }
            >>> ProcessConf.set_output_size(output_format)
            >>> {'fixed_scale': 2}
        """
        result = {}
        if Ut.is_dict(output_format, not_null=True):
            if ProcessConf.is_fixed_width_or_height(output_format):
                result.update({
                    'fixed_width': output_format.get('fixed_width'),
                    'fixed_height': output_format.get('fixed_height')
                })
            elif ProcessConf.is_fixed_size(output_format):
                result.update({
                    'fixed_width': output_format.get('fixed_size'),
                    'fixed_height': output_format.get('fixed_size')
                })
            elif ProcessConf.is_fixed_scale(output_format):
                result.update({
                    'fixed_scale': output_format.get('fixed_scale')
                })

        return result

    @staticmethod
    def is_output_write_jpg_format(data: dict) -> bool:
        """
        Check if a given output configuration contains valid options for writing JPEG format.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains valid JPEG format options, False otherwise.
        :rtype: bool

        Example:
            >>> config = {'ext': '.jpg', 'quality': 90, 'progressive': 1}
            >>> ProcessConf.is_output_write_jpg_format(config)
            >>> True
        """
        return Ut.is_str(data.get('ext')) \
            and ImageToolsHelper.is_valid_jpg_ext(data.get('ext')) \
            and (Ut.is_int(data.get('quality'), mini=0, maxi=100)
                 or data.get('quality') is None) \
            and (Ut.is_int(data.get('progressive'), mini=0, maxi=1)
                 or data.get('progressive') is None) \
            and (Ut.is_int(data.get('optimize'), mini=0, maxi=1)
                 or data.get('optimize') is None)

    @staticmethod
    def is_output_write_webp_format(data: dict) -> bool:
        """
        Check if a given output configuration contains valid options for writing WebP format.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains valid WebP format options, False otherwise.
        :rtype: bool

        Example:
            >>> config = {'ext': '.webp', 'quality': 80}
            >>> ProcessConf.is_output_write_webp_format(config)
            >>> True
        """
        return Ut.is_str(data.get('ext')) \
            and data.get('ext').lower() == '.webp' \
            and (Ut.is_int(data.get('quality'), mini=0, maxi=100)
                 or data.get('quality') is None)

    @staticmethod
    def is_output_write_png_format(data: dict) -> bool:
        """
        Check if a given output configuration contains valid options for writing PNG format.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains valid PNG format options, False otherwise.
        :rtype: bool

        Example:
            >>> config = {'ext': '.png', 'compression': 6}
            >>> ProcessConf.is_output_write_png_format(config)
            >>> True
        """
        return Ut.is_str(data.get('ext')) \
            and data.get('ext').lower() == '.png' \
            and (Ut.is_int(data.get('compression'), mini=0, maxi=9)
                 or data.get('compression') is None)

    @staticmethod
    def is_valid_output_format(data: dict) -> bool:
        """
        Check if a given output configuration contains valid options for writing image formats.

        :param data: The output configuration data.
        :type data: dict

        :return: True if the configuration contains valid image format options, False otherwise.
        :rtype: bool

        Example:
            >>> config = {'ext': '.jpg', 'quality': 90, 'progressive': 1}
            >>> ProcessConf.is_valid_output_format(config)
            >>> True
        """
        return ImageToolsHelper.is_valid_image_ext(data.get('ext')) \
            and (ProcessConf.is_output_write_jpg_format(data)
                 or ProcessConf.is_output_write_webp_format(data)
                 or ProcessConf.is_output_write_png_format(data))

    @staticmethod
    def set_output_format(write_formats: list) -> dict or None:
        """
        Set the write_format configuration.

        :param write_formats: List of output formats to be written.
        :type write_formats: list

        :return: The write_format configuration dictionary.
        :rtype: dict or None

        Example:
            >>> format_list = [{'ext': '.jpg', 'quality': 90}, {'ext': '.png', 'compression': 6}]
            >>> ProcessConf.set_output_format(format_list)
            >>> {'formats': [{'ext': '.jpg', 'quality': 90}, {'ext': '.png', 'compression': 6}]}
        """
        result = None
        if Ut.is_list(write_formats, not_null=True):
            for write_format in write_formats:
                if not ProcessConf.is_valid_output_format(write_format):
                    raise SettingInvalidException(
                        "[ImageTools::set_output_format] "
                        "Error: Invalid output format configuration. "
                        "Bad extensions or write output options: %s",
                        write_format
                    )
            result = {'formats': write_formats}
        return result
