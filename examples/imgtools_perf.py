"""
ImageTools unittest class.

Use pytest package.
"""
import logging
import argparse
import sys
import time
from numpy import ndarray
from os import path
from imgtools_m8 import configure_logging
from imgtools_m8.img_tools import ImageTools

logging.basicConfig()
logger = logging.getLogger("imgtools_m8")

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestExample:
    """Test Image Tools example class """
    def __init__(self):
        self.source_path = path.join(path.dirname(__file__), 'source')
        self.output_path = path.join(path.dirname(__file__), 'output')
        self.i_tool = None
        logger.setLevel(logging.INFO)

    def init_imgtools(self):
        """Init image tools class"""
        start = time.perf_counter()
        output_formats = [
            {
                'fixed_width': 100,
                'formats': [
                    {'ext': '.png', 'compression': 0}
                ]
            }
        ]

        self.i_tool = ImageTools(
            source_path=self.source_path,
            output_path=self.output_path,
            output_formats=output_formats
        )
        logger.info(
            "[TestExample] Init Image tools class in %s s",
            time.perf_counter() - start
        )

    def run_reduce(self):
        """Reduce image source"""
        start = time.perf_counter()
        self.i_tool.run()
        logger.info(
            "[TestExample] Reduce and write Image in %s s",
            time.perf_counter() - start
        )

    def open_reduced_image(self):
        """Open reduced image"""
        start = time.perf_counter()
        file_name = 'pagoda_100x56.png'
        self.i_tool.set_source_path(
            source_path=path.join(
                self.output_path,
                file_name)
        )
        image = self.i_tool.read_image(source_path=self.i_tool.source_path)
        logger.info(
            "[TestExample] Open %s image in %s s",
            file_name,
            time.perf_counter() - start,
        )
        return image

    def load_model_from_scale(self, scale: int):
        """Load model from scale"""
        start = time.perf_counter()
        self.i_tool.expander.model_conf.set_scale(scale)
        self.i_tool.expander.load_model()
        logger.info(
            "[TestExample] Load x%s model in %s s",
            scale,
            time.perf_counter() - start,
        )

    def upscale_image(self,
                      image: ndarray,
                      scale: int
                      ) -> ndarray:
        """Upscale image once"""
        start = time.perf_counter()
        image_up = self.i_tool.expander.upscale_and_write_images(image)
        logger.info(
            "[TestExample] Upscale image x%s in %s s",
            scale,
            time.perf_counter() - start,
        )
        return image_up

    def write_image(self,
                    image: ndarray,
                    file_name: str
                    ):
        """write image"""
        start = time.perf_counter()
        self.i_tool.write_image_format(
            image=image,
            output_path=self.output_path,
            file_name=file_name,
            output_format={'ext': '.png', 'compression': 0}
        )
        logger.info(
            "[TestExample] Write %s image in %s s",
            file_name,
            time.perf_counter() - start,
        )

    def test_models(self, image):
        """Test upscale models"""
        start = time.perf_counter()
        # upscale with edsr_x2 model
        self.load_model_from_scale(scale=2)
        image_up = self.upscale_image(
            image=image,
            scale=2
        )
        self.write_image(
            image=image_up,
            file_name='pagoda_x2.png'
        )

        # upscale with edsr_x3 model
        self.load_model_from_scale(scale=3)
        image_up = self.upscale_image(
            image=image,
            scale=3
        )
        self.write_image(
            image=image_up,
            file_name='pagoda_x3.png'
        )

        # upscale with edsr_x4 model
        self.load_model_from_scale(scale=4)
        image_up = self.upscale_image(
            image=image,
            scale=4
        )
        self.write_image(
            image=image_up,
            file_name='pagoda_x4.png'
        )

        # upscale with edsr_x2 model two times
        self.load_model_from_scale(scale=2)
        image_up = self.upscale_image(
            image=image,
            scale=2
        )
        image_up = self.upscale_image(
            image=image_up,
            scale=2
        )
        self.write_image(
            image=image_up,
            file_name='pagoda_x2_x2.png'
        )

    def run(self):
        """Test example"""
        start = time.perf_counter()
        # init imgtools
        self.init_imgtools()
        # execute configuration
        # reduce image to 100px width and convert to png
        self.run_reduce()
        # open image test
        image = self.open_reduced_image()
        # init default model
        self.i_tool.init_expander_model()
        # test all edsr models
        self.test_models(image)


def parse_args(args):
    """
    Parsing function.

    Parse arguments used in example
    :param args: arguments passed from the command line
    :return: return parser
    """
    # create arguments
    arg_parser = argparse.ArgumentParser(description='imgtools_m8 example')
    arg_parser.add_argument('--debug', action='store_true', help='Show debug output')

    # parse arguments from script parameters
    return arg_parser.parse_args(args)


if __name__ == '__main__':

    parser = parse_args(sys.argv[1:])

    configure_logging(parser.debug)

    i_tool = TestExample()
    i_tool.run()

