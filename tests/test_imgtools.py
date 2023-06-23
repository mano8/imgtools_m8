"""
SerialUtils unittest class.

Use pytest package.
"""
import os
from numpy import ndarray
from imgtools_m8.imgtools import ImageExpander

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestSerialUtils:

    def setup_method(self):
        """
        Setup any state tied to the execution of the given function.

        Invoked for every test function in the module.
        """
        model_conf = {
            'path': os.path.join(os.path.abspath('..'), 'models'),
            'file_name': 'EDSR_x2.pb',
            'model_name': 'edsr',
            'scale': 2
        }
        source_path = os.path.join(os.path.abspath('.'), 'dummy_dir')
        output_conf = {
            'path': os.path.join(os.path.abspath('.'), 'dummy_output'),
             'ext': '.png',
            'fixed_width': 450,
            'fixed_height': 450,
        }

        self.obj = ImageExpander(
            model_conf=model_conf,
            source_path=source_path,
            output_conf=output_conf
        )

    def test_run(self):
        """Test run method"""
        tst = self.obj.run()
        assert tst is True


    @staticmethod
    def test_is_model_conf():
        """Test is_model_conf method"""

    @staticmethod
    def test_is_output_conf():
        """Test is_output_conf method"""

    @staticmethod
    def test_read_image():
        """Test read_image method"""
        image = ImageExpander.read_image(os.path.join('dummy_dir', 'recien_llegado.jpg'))
        assert type(image) == ndarray
        assert image.shape[:2] == (216, 340)

    @staticmethod
    def test_get_image_size():
        """Test get_image_size method"""
        image = ImageExpander.read_image(os.path.join('dummy_dir', 'recien_llegado.jpg'))
        size = ImageExpander.get_image_size(image)
        assert size == (216, 340)

    @staticmethod
    def test_image_resize():
        """Test image_resize method"""
        image = ImageExpander.read_image(os.path.join('dummy_dir', 'recien_llegado.jpg'))
        resized = ImageExpander.image_resize(image, width=200)
        assert image.shape[:2] == (216, 340)
        assert resized.shape[:2] == (127, 200)
        resized = ImageExpander.image_resize(image, height=200)
        assert resized.shape[:2] == (200, 314)

    @staticmethod
    def test_get_files_list():
        """Test get_files_list method"""
        files = ImageExpander.get_files_list('dummy_dir')
        assert len(files) == 3
        files = ImageExpander.get_files_list('dummy_dir', ext='.jpg')
        assert len(files) == 1
        files = ImageExpander.get_files_list('dummy_dir', ext=['.jpg', '.txt'])
        assert len(files) == 3

    @staticmethod
    def test_is_valid_image_ext():
        """Test is_valid_image_ext method"""
        assert not ImageExpander.is_valid_image_ext(ext='EDSR_x2.pb')
        assert not ImageExpander.is_valid_image_ext(ext='.pb')
        assert ImageExpander.is_valid_image_ext(ext='.jpeg')
        assert ImageExpander.is_valid_image_ext(ext='.jPeG')
        assert ImageExpander.is_valid_image_ext(ext='.jPG')
        assert ImageExpander.is_valid_image_ext(ext='.png')

    @staticmethod
    def test_cut_file_name():
        """Test cut_file_name method"""
        assert ImageExpander.cut_file_name(file_name='EDSR_x2.pb') == ('EDSR_x2', '.pb')
        assert ImageExpander.cut_file_name(file_name='img.jpg') == ('img', '.jpg')
        assert ImageExpander.cut_file_name(file_name='img') == ('img', '')
        assert ImageExpander.cut_file_name(file_name='img.tar.gz') == ('img.tar', '.gz')
        assert ImageExpander.cut_file_name(file_name='img.back.tar.gz', ext_len=2) == ('img.back', '.tar.gz')
        assert ImageExpander.cut_file_name(file_name='img.back.tar.gz', ext_len=0) == ('img', '.back.tar.gz')

    @staticmethod
    def test_get_extension():
        """Test get_extension method"""
        assert ImageExpander.get_extension(path='EDSR_x2.pb') == '.pb'
        assert ImageExpander.get_extension(path='img.jpg') == '.jpg'
        assert ImageExpander.get_extension(path='img') == ''
        assert ImageExpander.get_extension(path='img.tar.gz') == '.gz'
        assert ImageExpander.get_extension(path='img.back.tar.gz', ext_len=2) == '.tar.gz'
        assert ImageExpander.get_extension(path='img.tar.gz.sav', ext_len=3) == '.tar.gz.sav'
        assert ImageExpander.get_extension(path='img.tar.gz', ext_len=3) == '.tar.gz'
