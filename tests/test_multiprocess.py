"""
ImageTools unittest class.

Use pytest package.
"""
from os import path
from .helper import HelperTest
from imgtools_m8.multiprocess import MultiProcessImage

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
                'fixed_width': 260,
                'fixed_height': 200,
                'formats': [
                    {'ext': '.jpg', 'quality': 80}
                ]
            }
        ]
        self.obj = MultiProcessImage(
            source_path=HelperTest.get_source_path(),
            output_path=HelperTest.get_output_path(),
            output_formats=output_formats
        )

    def test_run_multiple(self):
        """Test run_multiple method"""
        tst = self.obj.run_multiple()
        # unable to upscale bad_image.jpg
        assert tst is False

        self.obj.set_source_path(
            source_path=path.join(
                HelperTest.get_source_path(),
                'good'
            )
        )

        tst = self.obj.run_multiple()
        # unable to upscale bad_image.jpg
        assert tst is True
