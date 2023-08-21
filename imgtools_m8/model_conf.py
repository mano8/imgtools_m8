"""IModel Configuration class"""
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


class ModelConf:
    """
    Model configuration parameters.
    """
    def __init__(self,
                 model_path: str or None = None,
                 model_name: str or None = None,
                 scale: int or None = None
                 ):
        self.model_name = None
        self.model_path = None
        self.scale = None
        self.set_model_path(model_path)
        self.set_model_name(model_name)
        self.set_scale(scale)

    def is_ready(self) -> bool:
        """Test if is_ready"""
        return self.has_model_path() \
            and self.has_model_name() \
            and self.has_scale()

    def has_model_path(self) -> bool:
        """Test if instance has valid model name"""
        return ModelConf.is_model_path(self.model_path)

    def set_model_path(self, value: str) -> bool:
        """Set model name"""
        result = False
        self.model_path = None
        if ModelConf.is_model_path(value):
            self.model_path = value
            result = True
        return result

    def get_path(self) -> str:
        """Get model path"""
        return self.model_path

    def has_model_name(self) -> bool:
        """Test if instance has valid model name"""
        return ModelConf.is_model_name(self.model_name)

    def set_model_name(self, value: str) -> bool:
        """Set model name"""
        result = False
        self.model_name = None
        if ModelConf.is_model_name(value):
            self.model_name = value
            result = True
        return result

    def get_model_name(self) -> str:
        """Get model_name"""
        return self.model_name

    def has_scale(self) -> bool:
        """Test if instance has valid model name"""
        return ModelConf.is_scale(
            model_path=self.model_path,
            model_name=self.model_name,
            scale=self.scale
        )

    def set_scale(self, value: int or None, set_default: bool = True) -> bool:
        """Set model name"""
        result = False
        self.scale = None
        scale_list = ModelConf.get_model_scales_available(
            path=self.model_path,
            model_name=self.model_name
        )
        if ModelConf.is_scale_in_list(
                scale_list=scale_list,
                scale=value):
            self.scale = value
            result = True
        elif not Ut.is_int(value, mini=1) \
                and set_default is True\
                and Ut.is_list(scale_list, not_null=True):
            self.scale = scale_list[0]
            result = True

        return result

    def get_scale(self) -> int:
        """Get scale"""
        return self.scale

    def get_available_scales(self) -> list:
        """Get scale"""
        return ModelConf.get_model_scales_available(
            path=self.model_path,
            model_name=self.model_name
        )

    def get_file_name(self) -> str:
        """Get scale"""
        return ModelConf.get_model_file_name(
            path=self.model_path,
            model_name=self.model_name,
            scale=self.scale
        )

    @staticmethod
    def get_valid_model_names() -> list:
        """Get valid model names"""
        return [
            'edsr', 'espcn', 'fsrcnn', 'lapsrn'
        ]

    @staticmethod
    def is_model_name(value: str) -> bool:
        """Test if valid model name"""
        return Ut.is_str(value) \
            and value in ModelConf.get_valid_model_names()

    @staticmethod
    def is_model_path(value: str) -> bool:
        """Test if valid model_path"""
        return Ut.is_str(value, not_null=True) \
            and Path.isdir(value)

    @staticmethod
    def get_models_list(path: str) -> list:
        """List directory files"""
        result = ImageToolsHelper.get_files_list(path, ext='.pb')
        if Ut.is_list(result, not_null=True):
            result.sort()
        return result

    @staticmethod
    def get_model_scale(file_name: str) -> int:
        """Get model scale number"""
        result = 0
        if Ut.is_str(file_name, not_null=True):
            name, ext = ImageToolsHelper.cut_file_name(file_name)
            result = Ut.get_int(name[-1:], default=0)
        return result

    @staticmethod
    def get_model_scales_available(path: str,
                                   model_name: str
                                   ) -> list or None:
        """Get available model scale list."""
        result, models = None, ModelConf.get_models_list(path)
        is_valid_model_name = ModelConf.is_model_name(model_name)
        if Ut.is_list(models, not_null=True) \
                and is_valid_model_name:
            result = []
            for file_name in models:
                if model_name in file_name.lower():
                    scale = ModelConf.get_model_scale(file_name)
                    if scale > 0:
                        result.append(scale)
            result.sort()
        else:
            result = None
        return result

    @staticmethod
    def get_model_file_name(path: str,
                            model_name: str,
                            scale: int
                            ) -> str or None:
        """Get model file name."""
        result, models = None, ModelConf.get_models_list(path)
        is_valid_model_name = ModelConf.is_model_name(model_name)
        if Ut.is_list(models, not_null=True) \
                and is_valid_model_name:
            for file_name in models:
                if model_name in file_name.lower():
                    model_scale = ModelConf.get_model_scale(file_name)
                    if scale == model_scale:
                        result = file_name
                        break
        else:
            result = None
        return result

    @staticmethod
    def is_model_file_name(model_path: str or None,
                           file_name: str or None
                           ) -> bool:
        """Test if valid model file_name"""
        return Ut.is_str(file_name, not_null=True) \
            and ImageToolsHelper.get_extension(
                path=file_name) == '.pb' \
            and Ut.is_str(model_path, not_null=True) \
            and Path.isfile(
                Path.join(model_path, file_name)
            )

    @staticmethod
    def is_scale_in_list(scale_list: list,
                         scale: int
                         ) -> bool:
        """Test if valid model_path"""
        return Ut.is_list(scale_list, not_null=True) \
            and Ut.is_int(scale, mini=2) \
            and scale in scale_list

    @staticmethod
    def is_scale(model_path: str,
                 model_name: str,
                 scale: int,
                 ) -> bool:
        """Test if valid scale"""
        result = False
        scale_list = ModelConf.get_model_scales_available(
            path=model_path,
            model_name=model_name
        )
        if ModelConf.is_scale_in_list(
                scale_list=scale_list,
                scale=scale):
            result = True
        return result
