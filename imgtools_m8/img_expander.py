from cv2 import dnn_superres
from numpy import ndarray
import os
from ve_utils.utils import UType as Ut
from imgtools_m8.model_conf import ModelConf
from imgtools_m8.helper import ImageToolsHelper

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class ImageExpander:
    """
    Image expander Tool
    """
    def __init__(self,
                 model_conf: dict or None = None,
                 ):
        self.model_conf = None
        self.sr = None
        self.set_model_conf(model_conf)

    def is_ready(self) -> bool:
        """Test if is_ready"""
        return self.has_model_conf() \
            and self.sr is not None

    def has_model_conf(self) -> bool:
        """Test if instance has model_conf"""
        return self.model_conf.is_ready()

    def set_model_conf(self,
                       model_conf: dict or None = None
                       ) -> bool:
        """Set model configuration"""
        model_path = ImageToolsHelper.get_package_models_path()
        model_name = 'edsr'
        scale = 2
        if Ut.is_dict(model_conf, not_null=True):

            if ModelConf.is_model_path(model_conf.get('path')):
                model_path = model_conf.get('path')

            if ModelConf.is_model_name(model_conf.get('model_name')):
                model_name = model_conf.get('model_name')

            if ModelConf.is_scale(
                    model_path=model_path,
                    model_name=model_name,
                    scale=model_conf.get('scale')):
                scale = model_conf.get('scale')

        self.model_conf = ModelConf(
            model_path=model_path,
            model_name=model_name,
            scale=scale
        )
        test = self.model_conf.is_ready()
        return test

    def init_sr(self):
        """Init sr"""
        self.sr = dnn_superres.DnnSuperResImpl_create()

    def load_model(self):
        """Load model"""
        test = False
        if self.has_model_conf():
            mod_path = os.path.join(
                self.model_conf.get_path(),
                self.model_conf.get_file_name()
            )
            if os.path.isfile(mod_path):
                self.sr.readModel(mod_path)
                # Set the desired model and scale to get correct pre- and post-processing
                self.sr.setModel(
                    self.model_conf.get_model_name(),
                    self.model_conf.get_scale()
                )
                test = True
        return test

    def many_image_upscale(self,
                           image: ndarray,
                           nb_upscale: int
                           ) -> ndarray or None:
        """Upscale image x times."""
        max_upscale = 10
        if image is not None\
                and Ut.is_int(nb_upscale, mini=1, maxi=max_upscale):
            counter = 0
            while counter < nb_upscale and counter <= max_upscale:
                image = self.sr.upsample(image)
                counter += 1
        return image

    @staticmethod
    def get_models_list(path):
        """List directory files"""
        return ImageToolsHelper.get_files_list(path, ext='.pb')

    @staticmethod
    def get_model_scale(file_name: str) -> int:
        """Get model scale number"""
        result = 0
        if Ut.is_str(file_name, not_null=True):
            name, ext = ImageToolsHelper.cut_file_name(file_name)
            result = Ut.get_int(name[-1:], default=0)
        return result

    @staticmethod
    def get_model_name(file_name: str) -> str or None:
        """Get model name"""
        result = None
        if Ut.is_str(file_name, not_null=True):
            name, ext = ImageToolsHelper.cut_file_name(file_name)
            result = name[:-3].lower()
        return result

    @staticmethod
    def is_model_path(model_path: str) -> bool:
        """Test if valid model_path"""
        return Ut.is_str(model_path, not_null=True) \
            and os.path.isdir(model_path)

    @staticmethod
    def is_file_name(model_path: str,
                     file_name: str) -> bool:
        """Test if valid model file_name"""
        return Ut.is_str(file_name, not_null=True) \
            and ImageToolsHelper.get_extension(
                path=file_name) == '.pb'\
            and Ut.is_str(model_path, not_null=True) \
            and os.path.isfile(
                os.path.join(model_path, file_name)
            )

    @staticmethod
    def is_model_name(model_name: str,
                      file_name: str
                      ) -> bool:
        """Test if valid model_name"""
        return Ut.is_str(model_name, not_null=True) \
            and model_name == ImageExpander.get_model_name(
                file_name)

    @staticmethod
    def is_scale(scale: int,
                 file_name: str
                 ) -> bool:
        """Test if valid model_name"""
        return Ut.is_int(scale, mini=2, maxi=8) \
            and scale == ImageExpander.get_model_scale(
                file_name)

    @staticmethod
    def is_model_conf(model_conf: dict) -> bool:
        """Test if valid model conf"""
        return Ut.is_dict(model_conf) \
            and ImageExpander.is_model_path(
                model_path=model_conf.get('path')) \
            and ImageExpander.is_file_name(
                file_name=model_conf.get('file_name'),
                model_path=model_conf.get('path')
            ) \
            and ImageExpander.is_model_name(
                model_name=model_conf.get('model_name'),
                file_name=model_conf.get('file_name')) \
            and ImageExpander.is_scale(
                scale=model_conf.get('scale'),
                file_name=model_conf.get('file_name')
            )
