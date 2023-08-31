"""Model Configuration class"""
import logging
from enum import Enum
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


class ScaleSelector(Enum):
    """
    Enumeration class for selecting different scaling strategies.

    Attributes:
        AUTO_SCALE (int): Represents automatic scale selection.
        FIXED_SCALE (int): Represents fixed scale selection.
    """
    AUTO_SCALE = 0
    FIXED_SCALE = 1


class ModelConf:
    """
    Model configuration parameters.

    Attributes:
        model_name (str): The name of the model.
        model_path (str): The path to the model directory.
        scale (int): The scale of the model.
        scale_selector (ScaleSelector): The scale selection strategy.
    """
    def __init__(self,
                 model_path: str or None = None,
                 model_name: str or None = None,
                 scale: int or None = None,
                 scale_selector: ScaleSelector = ScaleSelector.AUTO_SCALE
                 ):
        """
        Initialize the ModelConf instance.

        :param model_path: The path to the model directory.
        :type model_path: str, optional
        :param model_name: The name of the model.
        :type model_name: str, optional
        :param scale: The scale of the model.
        :type scale: int, optional
        :param scale_selector: The scale selection strategy.
        :type scale_selector: ScaleSelector, optional
        """
        self.model_name = None
        self.model_path = None
        self.scale = None
        self.scale_selector = ScaleSelector.AUTO_SCALE
        self.set_model_path(model_path)
        self.set_model_name(model_name)
        self.set_scale(scale)
        self.set_scale_selector(scale_selector)

    def is_ready(self) -> bool:
        """
        Check if the ModelConf instance is ready.

        :return: True if all required attributes are set, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf(model_path='path/to/model', model_name='model_name', scale=2)
            >>> conf.is_ready()
            True
        """
        return self.has_model_path() \
            and self.has_model_name() \
            and self.has_scale()

    def has_model_path(self) -> bool:
        """
        Check if the ModelConf instance has a valid model path.

        :return: True if the model path is valid, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf(model_path='path/to/model')
            >>> conf.has_model_path()
            True
        """
        return ModelConf.is_model_path(self.model_path)

    def set_model_path(self, value: str) -> bool:
        """
        Set the model path.

        :param value: The model path to be set.
        :type value: str

        :return: True if the model path was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf()
            >>> conf.set_model_path('path/to/model')
            True
        """
        result = False
        self.model_path = None
        if ModelConf.is_model_path(value):
            self.model_path = value
            result = True
        return result

    def get_path(self) -> str:
        """
        Get the model path.

        :return: The model path.
        :rtype: str

        Example:
            >>> conf = ModelConf(model_path='path/to/model')
            >>> conf.get_path()
            'path/to/model'
        """
        return self.model_path

    def has_model_name(self) -> bool:
        """
        Check if the ModelConf instance has a valid model name.

        :return: True if the model name is valid, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf(model_name='model_name')
            >>> conf.has_model_name()
            True
        """
        return ModelConf.is_model_name(self.model_name)

    def set_model_name(self, value: str) -> bool:
        """
        Set the model name.

        :param value: The model name to be set.
        :type value: str

        :return: True if the model name was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf()
            >>> conf.set_model_name('model_name')
            True
        """
        result = False
        self.model_name = None
        if ModelConf.is_model_name(value):
            self.model_name = value
            result = True
        return result

    def get_model_name(self) -> str:
        """
        Get the model name.

        :return: The model name.
        :rtype: str

        Example:
            >>> conf = ModelConf(model_name='model_name')
            >>> conf.get_model_name()
            'model_name'
        """
        return self.model_name

    def has_scale(self) -> bool:
        """
        Check if the ModelConf instance has a valid scale.

        :return: True if the scale is valid, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf(scale=2)
            >>> conf.has_scale()
            True
        """
        return ModelConf.is_scale(
            model_path=self.model_path,
            model_name=self.model_name,
            scale=self.scale
        )

    def set_scale(self, value: int or None, set_default: bool = True) -> bool:
        """
        Set the model scale.

        :param value: The scale value to be set.
        :type value: int or None
        :param set_default: Whether to set a default scale if the provided value is not valid.
        :type set_default: bool, optional

        :return: True if the scale was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf()
            >>> conf.set_scale(2)
            True
        """
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
        """
        Get the model scale.

        :return: The model scale.
        :rtype: int

        Example:
            >>> conf = ModelConf(scale=2)
            >>> conf.get_scale()
            2
        """
        return self.scale

    def has_scale_selector(self) -> bool:
        """
        Check if the ModelConf instance has a valid scale selection strategy.

        :return: True if the scale selection strategy is valid, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf(scale_selector=ScaleSelector.AUTO_SCALE)
            >>> conf.has_scale_selector()
            True
        """
        return ModelConf.is_scale_selector(self.scale_selector)

    def set_scale_selector(self, value: ScaleSelector) -> bool:
        """
        Set the scale selection strategy.

        :param value: The scale selection strategy to be set.
        :type value: ScaleSelector

        :return: True if the scale selection strategy was set successfully, False otherwise.
        :rtype: bool

        Example:
            >>> conf = ModelConf()
            >>> conf.set_scale_selector(value=ScaleSelector.AUTO_SCALE)
            True
        """
        result = False
        self.scale_selector = 0
        if ModelConf.is_scale_selector(value):
            self.scale_selector = value
            result = True
        return result

    def get_scale_selector(self) -> ScaleSelector:
        """
        Get the scale selection strategy.

        :return: The scale selection strategy.
        :rtype: ScaleSelector

        Example:
            >>> conf = ModelConf(scale_selector=ScaleSelector.AUTO_SCALE)
            >>> conf.get_scale_selector()
            ScaleSelector.AUTO_SCALE
        """
        return self.scale_selector

    def get_available_scales(self) -> list:
        """
        Get a list of available scales for the model.

        :return: A list of available scales.
        :rtype: list

        Example:
            >>> conf = ModelConf(model_path='/path/to/models', model_name='edsr')
            >>> conf.get_available_scales()
            [2, 3, 4]
        """
        return ModelConf.get_model_scales_available(
            path=self.model_path,
            model_name=self.model_name
        )

    def get_file_name(self) -> str:
        """
        Get the model file name based on configuration.

        :return: The model file name.
        :rtype: str

        Example:
            >>> conf = ModelConf(model_path='/path/to/models', model_name='edsr', scale=2)
            >>> conf.get_file_name()
            'edsr_x2'
        """
        return ModelConf.get_model_file_name(
            path=self.model_path,
            model_name=self.model_name,
            scale=self.scale
        )

    @staticmethod
    def get_valid_model_names() -> list:
        """
        Get a list of valid model names.

        :return: A list of valid model names.
        :rtype: list

        Example:
            >>> ModelConf.get_valid_model_names()
            ['edsr', 'espcn', 'fsrcnn', 'lapsrn']
        """
        return [
            'edsr', 'espcn', 'fsrcnn', 'lapsrn'
        ]

    @staticmethod
    def is_model_name(value: str) -> bool:
        """
        Check if a given value is a valid model name.

        :param value: The value to be checked.
        :type value: str

        :return: True if the value is a valid model name, False otherwise.
        :rtype: bool

        Example:
            >>> ModelConf.is_model_name('edsr')
            True
            >>> ModelConf.is_model_name('invalid_model')
            False
        """
        return Ut.is_str(value) \
            and value in ModelConf.get_valid_model_names()

    @staticmethod
    def is_model_path(value: str) -> bool:
        """
        Check if a given value is a valid model path.

        :param value: The value to be checked.
        :type value: str

        :return: True if the value is a valid model path, False otherwise.
        :rtype: bool

        Example:
            >>> ModelConf.is_model_path('/path/to/models')
            True
            >>> ModelConf.is_model_path('/invalid/path')
            False
        """
        return Ut.is_str(value, not_null=True) \
            and Path.isdir(value)

    @staticmethod
    def get_models_list(path: str) -> list:
        """
        Get a list of model files from the specified path.

        :param path: The path to the directory containing model files.
        :type path: str

        :return: A list of model file names.
        :rtype: list

        Example:
            >>> ModelConf.get_models_list('/path/to/models')
            ['model1.pb', 'model2.pb']
        """
        result = ImageToolsHelper.get_files_list(path, ext='.pb')
        if Ut.is_list(result, not_null=True):
            result.sort()
        return result

    @staticmethod
    def get_model_scale(file_name: str) -> int:
        """
        Get the model scale number from a model file name.

        :param file_name: The model file name.
        :type file_name: str

        :return: The model scale number extracted from the file name, or 0 if not found.
        :rtype: int

        Example:
            >>> ModelConf.get_model_scale('model1.pb')
            1
            >>> ModelConf.get_model_scale('model2.pb')
            2
        """
        result = 0
        if Ut.is_str(file_name, not_null=True):
            name, ext = ImageToolsHelper.cut_file_name(file_name)
            result = Ut.get_int(name[-1:], default=0)
        return result

    @staticmethod
    def get_model_scales_available(path: str,
                                   model_name: str
                                   ) -> list or None:
        """
        Get a list of available model scales for a given model name and path.

        :param path: The path to the directory containing model files.
        :type path: str
        :param model_name: The model name.
        :type model_name: str

        :return: A list of available model scales, or None if no valid models are found.
        :rtype: list or None

        Example:
            >>> ModelConf.get_model_scales_available('/path/to/models', 'edsr')
            [1, 2, 3]
        """
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
        """
        Get the model file name for a specific model name and scale.

        :param path: The path to the directory containing model files.
        :type path: str
        :param model_name: The model name.
        :type model_name: str
        :param scale: The desired model scale.
        :type scale: int

        :return: The model file name matching the model name and scale, or None if not found.
        :rtype: str or None

        Example:
            >>> ModelConf.get_model_file_name('/path/to/models', 'edsr', 2)
            'edsr_x2.pb'
        """
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
        """
        Check if a given file name is a valid model file name.

        :param model_path: The path to the directory containing model files.
        :type model_path: str or None
        :param file_name: The file name to check.
        :type file_name: str or None

        :return: True if the file name is a valid model file name, False otherwise.
        :rtype: bool

        Example:
            >>> ModelConf.is_model_file_name('/path/to/models', 'edsr_x2.pb')
            True
        """
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
        """
        Check if a given scale is present in the provided scale list.

        :param scale_list: A list of available scales.
        :type scale_list: list
        :param scale: The scale to check.
        :type scale: int

        :return: True if the scale is in the list, False otherwise.
        :rtype: bool

        Example:
            >>> ModelConf.is_scale_in_list([2, 3, 4], 3)
            True
        """
        return Ut.is_list(scale_list, not_null=True) \
            and Ut.is_int(scale, mini=2) \
            and scale in scale_list

    @staticmethod
    def is_scale(model_path: str,
                 model_name: str,
                 scale: int,
                 ) -> bool:
        """
        Check if a given scale is valid for the specified model path and name.

        :param model_path: The path to the directory containing model files.
        :type model_path: str
        :param model_name: The model name.
        :type model_name: str
        :param scale: The scale to check.
        :type scale: int

        :return: True if the scale is valid for the model path and name, False otherwise.
        :rtype: bool

        Example:
            >>> ModelConf.is_scale('/path/to/models', 'edsr', 2)
            True
        """
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

    @staticmethod
    def is_scale_selector(value: ScaleSelector) -> bool:
        """
        Check if the given value is a valid ScaleSelector enumeration.

        :param value: The value to check.
        :type value: ScaleSelector

        :return: True if the value is a valid ScaleSelector enumeration, False otherwise.
        :rtype: bool

        Example:
            >>> value = ScaleSelector.AUTO_SCALE
            >>> ModelConf.is_scale_selector(value)
            True
        """
        return isinstance(value, ScaleSelector)
