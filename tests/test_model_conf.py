"""
ModelConf unittest class.

Use pytest package.
"""
from ve_utils.utils import UType as Ut
from imgtools_m8.model_conf import ModelConf
from imgtools_m8.helper import ImageToolsHelper

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestModelConf:

    def setup_method(self):
        """
        Setup any state tied to the execution of the given function.

        Invoked for every test function in the module.
        """
        self.obj = ModelConf(
            model_path=ImageToolsHelper.get_package_models_path(),
            model_name='edsr',
            scale=2
        )

    def test_is_ready(self):
        """Test is_ready method"""
        assert self.obj.is_ready() is True

    def test_set_model_path(self):
        """Test set_model_path method"""
        self.obj.model_path = None
        assert self.obj.has_model_path() is False
        assert self.obj.set_model_path(
            ImageToolsHelper.get_package_models_path()
        ) is True
        assert self.obj.get_path() == ImageToolsHelper.get_package_models_path()
        assert self.obj.has_model_path() is True
        assert self.obj.set_model_path('/bad_path') is False
        assert self.obj.has_model_path() is False

    def test_set_model_name(self):
        """Test set_model_name method"""
        self.obj.model_name = None
        assert self.obj.has_model_name() is False
        assert self.obj.set_model_name('edsr') is True
        assert self.obj.get_model_name() == 'edsr'
        assert self.obj.has_model_name() is True
        assert self.obj.set_model_name('bad_model') is False
        assert self.obj.has_model_name() is False

    def test_set_scale(self):
        """Test set_scale method"""
        self.obj.scale = None
        assert self.obj.has_scale() is False
        assert self.obj.set_scale(value=2) is True
        assert self.obj.has_scale() is True
        assert self.obj.set_scale(value=0, set_default=False) is False
        assert self.obj.has_scale() is False
        assert self.obj.set_scale(0, set_default=True) is True
        assert self.obj.has_scale() is True
        assert self.obj.get_scale() == 2
        assert self.obj.get_file_name() == "EDSR_x2.pb"

    @staticmethod
    def test_get_valid_model_names():
        """Test get_valid_model_names method"""
        assert ModelConf.get_valid_model_names() == ['edsr', 'espcn', 'fsrcnn', 'lapsrn']

    @staticmethod
    def test_is_model_name():
        """Test is_model_name method"""
        assert ModelConf.is_model_name(value='edsr') is True
        assert ModelConf.is_model_name(value='espcn') is True
        assert ModelConf.is_model_name(value='fsrcnn') is True
        assert ModelConf.is_model_name(value='lapsrn') is True
        assert ModelConf.is_model_name(value='bad_model') is False

    @staticmethod
    def test_is_model_path():
        """Test is_model_path method"""
        assert ModelConf.is_model_path(
            value=ImageToolsHelper.get_package_models_path()
        ) is True
        assert ModelConf.is_model_path('/bad/path') is False

    @staticmethod
    def test_get_models_list():
        """Test get_models_list method"""
        assert len(ModelConf.get_models_list(
            path=ImageToolsHelper.get_package_models_path()
        )) == 3

    @staticmethod
    def test_get_model_scale():
        """Test get_model_scale method"""
        models = ModelConf.get_models_list(
            path=ImageToolsHelper.get_package_models_path()
        )
        assert ModelConf.get_model_scale(
            file_name=models[0]
        ) == 2

    @staticmethod
    def test_get_model_scales_available():
        """Test get_model_scales_available method"""
        scale_list = ModelConf.get_model_scales_available(
            path=ImageToolsHelper.get_package_models_path(),
            model_name='edsr'
        )
        assert Ut.is_list(scale_list, not_null=True) is True
        assert len(scale_list) == 3
        assert ModelConf.is_scale_in_list(
            scale_list=scale_list,
            scale=2
        ) is True
        scale_list = ModelConf.get_model_scales_available(
            path='/bad/path',
            model_name='edsr'
        )
        assert scale_list is None

    @staticmethod
    def test_get_model_file_name():
        """Test get_model_file_name method"""
        file_name = ModelConf.get_model_file_name(
            path=ImageToolsHelper.get_package_models_path(),
            model_name='edsr',
            scale=2
        )
        assert file_name == "EDSR_x2.pb"
        assert ModelConf.is_model_file_name(
            model_path=ImageToolsHelper.get_package_models_path(),
            file_name=file_name
        ) is True
        file_name = ModelConf.get_model_file_name(
            path='/bad/path',
            model_name='edsr',
            scale=2
        )
        assert file_name is None
        assert ModelConf.is_model_file_name(
            model_path=ImageToolsHelper.get_package_models_path(),
            file_name=file_name
        ) is False

    @staticmethod
    def test_is_scale():
        """Test is_scale method"""
        is_scale = ModelConf.is_scale(
            model_path=ImageToolsHelper.get_package_models_path(),
            model_name='edsr',
            scale=2
        )
        assert is_scale is True
        is_scale = ModelConf.is_scale(
            model_path=ImageToolsHelper.get_package_models_path(),
            model_name='edsr',
            scale=12
        )
        assert is_scale is False