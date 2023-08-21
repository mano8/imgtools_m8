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
    """

    def __init__(self,
                 source_path: str,
                 output_formats: list,
                 output_path: str or None = None,
                 ):
        self.source_path = None
        self.output_formats = None
        self.output_path = None
        self.set_source_path(source_path)
        self.set_output_formats(output_formats)
        self.set_output_path(output_path)

    def is_ready(self) -> bool:
        """Test if is_ready"""
        return self.has_source_path() \
            and self.has_output_formats() \
            and self.has_output_path()

    def has_source_path(self) -> bool:
        """Test if instance has valid source_path"""
        return ProcessConf.is_source_path(self.source_path)

    def set_source_path(self, value: str) -> bool:
        """
        Set source_path
        Can be a directory or image path.
        """
        result = False
        self.source_path = None
        if ProcessConf.is_source_path(value):
            self.source_path = value
            result = True
        return result

    def get_source_path(self) -> str:
        """Get source_path"""
        return self.source_path

    def has_output_formats(self) -> bool:
        """Test if instance has valid output_formats"""
        return ProcessConf.is_output_formats(self.output_formats)

    def set_output_formats(self, data: list) -> bool:
        """Set output_formats"""
        result = False
        self.output_formats = None
        if ProcessConf.is_output_formats(data):
            self.output_formats = []
            for output_format in data:
                conf = ProcessConf.set_write_format(output_format.get('formats'))
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
        """Get output_formats"""
        return self.output_formats

    def has_output_path(self) -> bool:
        """Test if instance has valid output_path"""
        return ProcessConf.is_output_path(self.output_path)

    def set_output_path(self, value: str) -> bool:
        """Set output_path"""
        result = False
        self.output_path = None
        if ProcessConf.is_output_path(value):
            self.output_path = value
            result = True
        return result

    def get_output_path(self) -> str:
        """Get output_path"""
        return self.output_path

    @staticmethod
    def is_source_path(source_path: str) -> bool:
        """Test if valid source_path"""
        return Ut.is_str(source_path, not_null=True) \
            and (Path.isdir(source_path)
                 or Path.isfile(source_path))

    @staticmethod
    def is_output_path(output_path: str) -> bool:
        """Test if valid output_path"""
        return Ut.is_str(output_path, not_null=True) \
            and Path.isdir(output_path)

    @staticmethod
    def is_output_formats(output_formats: list) -> bool:
        """Test if valid output_formats"""
        return Ut.is_list(output_formats, not_null=True)

    @staticmethod
    def is_fixed_width_or_height(data: dict) -> bool:
        """Test if valid fixed_width or fixed_height output configuration"""
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
        """Test if valid fixed_size output configuration"""
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
        """Test if valid fixed_scale output configuration"""
        return Ut.is_int(data.get('fixed_scale'), mini=2, maxi=10)

    @staticmethod
    def is_fixed_scale(data: dict) -> bool:
        """Test if valid fixed_scale output configuration"""
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
        """Set output_formats"""
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
        """Test if valid output configuration options"""
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
        """Test if valid output configuration options"""
        return Ut.is_str(data.get('ext')) \
            and data.get('ext').lower() == '.webp' \
            and (Ut.is_int(data.get('quality'), mini=0, maxi=100)
                 or data.get('quality') is None)

    @staticmethod
    def is_output_write_png_format(data: dict) -> bool:
        """Test if valid output configuration options"""
        return Ut.is_str(data.get('ext')) \
            and data.get('ext').lower() == '.png' \
            and (Ut.is_int(data.get('compression'), mini=0, maxi=9)
                 or data.get('compression') is None)

    @staticmethod
    def is_output_write_formats(data: dict) -> bool:
        """Test if valid output configuration options"""
        return ImageToolsHelper.is_valid_image_ext(data.get('ext')) \
            and (ProcessConf.is_output_write_jpg_format(data)
                 or ProcessConf.is_output_write_webp_format(data)
                 or ProcessConf.is_output_write_png_format(data))

    @staticmethod
    def set_write_format(write_formats: list) -> dict or None:
        """Set write_format"""
        result = None
        if Ut.is_list(write_formats, not_null=True):
            for write_format in write_formats:
                if not ProcessConf.is_output_write_formats(write_format):
                    raise SettingInvalidException(
                        "[ImageTools::set_write_format] "
                        "Error: Invalid output format configuration. "
                        "Bad extensions or write output options: %s",
                        write_format
                    )
            result = {'formats': write_formats}
        return result
